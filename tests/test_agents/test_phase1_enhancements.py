"""Tests for Phase 1 multi-agent enhancements:

1. Executor task timeout and cancellation
2. Agent health monitoring (heartbeat + metrics)
3. Skill→Agent bridge (call_agent)
4. E2E multi-agent collaboration scenarios

Phase 1 多智能体增强测试：
1. 执行器任务超时与取消
2. Agent 健康监控（心跳 + 指标）
3. Skill→Agent 桥接（call_agent）
4. E2E 多智能体协作场景
"""

from __future__ import annotations

import asyncio
import time

import pytest

from agents.base_agent import AgentCard, AgentStatus, BaseAgent
from agents.context import AgentContext
from agents.executor import (
    ExecutionPlan,
    ExecutionTask,
    MultiAgentExecutor,
    TaskStatus,
)
from agents.health import AgentHealthMonitor, AgentMetrics
from agents.message import AgentMessage, MessageBus, MessageType
from agents.registry import AgentRegistry
from skills.base_skill import BaseSkill, SkillResult


# ---------------------------------------------------------------------------
# Test agents for Phase 1 scenarios
# ---------------------------------------------------------------------------

class EchoAgent(BaseAgent):
    """Simple echo agent for testing."""

    def get_capabilities(self) -> list[str]:
        return ["echo", "test"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        return message.reply({"echo": message.content, "agent_id": self.agent_id})


class SlowAgent(BaseAgent):
    """Agent that takes a configurable amount of time to respond."""

    def __init__(self, delay: float = 2.0, **kwargs):
        super().__init__(**kwargs)
        self.delay = delay

    def get_capabilities(self) -> list[str]:
        return ["slow_task"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        await asyncio.sleep(self.delay)
        return message.reply({"status": "done", "delay": self.delay})


class FailAgent(BaseAgent):
    """Agent that always raises an exception."""

    def get_capabilities(self) -> list[str]:
        return ["fail"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        raise RuntimeError("FailAgent always fails")


class CounterAgent(BaseAgent):
    """Agent that counts invocations."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.call_count = 0

    def get_capabilities(self) -> list[str]:
        return ["count", "compute"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        self.call_count += 1
        return message.reply({"count": self.call_count})


class PriorityAwareAgent(BaseAgent):
    """Agent that records which actions were invoked (for priority testing)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.invocation_order: list[str] = []

    def get_capabilities(self) -> list[str]:
        return ["priority_task"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "unknown")
        self.invocation_order.append(action)
        return message.reply({"action": action})


# ---------------------------------------------------------------------------
# Test Skill subclass for call_agent bridge testing
# ---------------------------------------------------------------------------

class BridgeTestSkill(BaseSkill):
    """Skill that delegates work to an agent via call_agent."""

    async def execute(self, params: dict) -> SkillResult:
        registry = params.get("_registry")
        agent_id = params.get("agent_id", "echo")
        action = params.get("action", "test")
        timeout = params.get("timeout", 30.0)

        result = await self.call_agent(
            agent_id=agent_id,
            action=action,
            params={"data": params.get("data", "hello")},
            registry=registry,
            timeout=timeout,
        )
        return SkillResult(success=True, data=result, steps_completed=["call_agent"])


# ===========================================================================
# 1. Executor Task Timeout Tests
# ===========================================================================

class TestExecutorTimeout:
    """Test per-task timeout support in MultiAgentExecutor."""

    def setup_method(self):
        self.registry = AgentRegistry()
        self.context = AgentContext()
        self.executor = MultiAgentExecutor(self.registry, self.context)

    @pytest.mark.asyncio
    async def test_task_completes_within_timeout(self):
        echo = EchoAgent(agent_id="fast")
        self.registry.register(echo)

        plan = ExecutionPlan(objective="fast task")
        plan.add_task(ExecutionTask(
            id="t1", agent_id="fast", action="test", timeout_sec=10.0,
        ))
        result = await self.executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        assert result.tasks[0].status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_task_timeout_fails(self):
        slow = SlowAgent(delay=5.0, agent_id="slow_agent")
        self.registry.register(slow)

        plan = ExecutionPlan(objective="timeout test")
        plan.add_task(ExecutionTask(
            id="t1", agent_id="slow_agent", action="slow_task",
            timeout_sec=0.1, max_retries=0,
        ))
        result = await self.executor.execute(plan)
        assert result.status == TaskStatus.FAILED
        assert result.tasks[0].status == TaskStatus.FAILED
        assert "timed out" in result.tasks[0].error

    @pytest.mark.asyncio
    async def test_task_timeout_with_retry(self):
        slow = SlowAgent(delay=5.0, agent_id="slow_retry")
        self.registry.register(slow)

        plan = ExecutionPlan(objective="timeout retry")
        plan.add_task(ExecutionTask(
            id="t1", agent_id="slow_retry", action="slow",
            timeout_sec=0.1, max_retries=1,
        ))
        result = await self.executor.execute(plan)
        assert result.tasks[0].status == TaskStatus.FAILED
        assert result.tasks[0].retries == 2  # 1 original + 1 retry

    @pytest.mark.asyncio
    async def test_task_default_timeout(self):
        task = ExecutionTask(id="t", agent_id="x", action="y")
        assert task.timeout_sec == 30.0

    def test_task_custom_timeout_in_dict(self):
        task = ExecutionTask(id="t", agent_id="x", action="y", timeout_sec=60.0)
        d = task.to_dict()
        assert d["timeout_sec"] == 60.0


# ===========================================================================
# 2. Executor Task Cancellation Tests
# ===========================================================================

class TestExecutorCancellation:
    """Test task and plan cancellation in MultiAgentExecutor."""

    def setup_method(self):
        self.registry = AgentRegistry()
        self.context = AgentContext()
        self.executor = MultiAgentExecutor(self.registry, self.context)

    def test_cancel_pending_plan(self):
        echo = EchoAgent(agent_id="cancel_echo")
        self.registry.register(echo)

        plan = self.executor.build_sequential_plan(
            "cancel test",
            [
                {"agent_id": "cancel_echo", "action": "step1"},
                {"agent_id": "cancel_echo", "action": "step2"},
            ],
        )
        # Cancel before execution
        cancelled = self.executor.cancel_plan(plan)
        assert cancelled.status == TaskStatus.FAILED
        for task in cancelled.tasks:
            assert task.cancelled is True
            assert task.status == TaskStatus.SKIPPED

    def test_cancelled_task_has_error_message(self):
        plan = ExecutionPlan(objective="cancel msg test")
        plan.add_task(ExecutionTask(id="t1", agent_id="x", action="y"))
        self.executor.cancel_plan(plan)
        assert plan.tasks[0].error == "Cancelled by user"

    def test_cancel_sets_completed_at(self):
        plan = ExecutionPlan(objective="timestamp test")
        plan.add_task(ExecutionTask(id="t1", agent_id="x", action="y"))
        before = time.time()
        self.executor.cancel_plan(plan)
        assert plan.completed_at >= before
        assert plan.tasks[0].completed_at >= before

    @pytest.mark.asyncio
    async def test_cancelled_task_skipped_during_execution(self):
        echo = EchoAgent(agent_id="exec_cancel")
        self.registry.register(echo)

        plan = ExecutionPlan(objective="cancel during exec")
        task = ExecutionTask(id="t1", agent_id="exec_cancel", action="test")
        task.cancelled = True
        plan.add_task(task)

        result = await self.executor.execute(plan)
        assert result.tasks[0].status == TaskStatus.SKIPPED
        assert "cancelled" in result.tasks[0].error.lower()

    def test_cancel_records_trace(self):
        plan = ExecutionPlan(objective="trace test")
        plan.add_task(ExecutionTask(id="t1", agent_id="x", action="y"))
        self.executor.cancel_plan(plan)
        trace = self.context.get_trace()
        assert any("plan_cancelled" in t["action"] for t in trace)


# ===========================================================================
# 3. Executor Priority Tests
# ===========================================================================

class TestExecutorPriority:
    """Test priority-based task ordering."""

    def test_task_default_priority(self):
        task = ExecutionTask(id="t", agent_id="x", action="y")
        assert task.priority == 1  # normal

    def test_task_custom_priority(self):
        task = ExecutionTask(id="t", agent_id="x", action="y", priority=3)
        assert task.priority == 3

    def test_priority_in_dict(self):
        task = ExecutionTask(id="t", agent_id="x", action="y", priority=2)
        d = task.to_dict()
        assert d["priority"] == 2

    @pytest.mark.asyncio
    async def test_higher_priority_runs_first_in_ready_batch(self):
        """When multiple tasks are ready, higher priority should run first."""
        registry = AgentRegistry()
        counter = CounterAgent(agent_id="prio_counter")
        registry.register(counter)

        plan = ExecutionPlan(objective="priority order test")
        plan.add_task(ExecutionTask(
            id="low", agent_id="prio_counter", action="low_prio", priority=0,
        ))
        plan.add_task(ExecutionTask(
            id="high", agent_id="prio_counter", action="high_prio", priority=3,
        ))
        plan.add_task(ExecutionTask(
            id="normal", agent_id="prio_counter", action="normal_prio", priority=1,
        ))

        executor = MultiAgentExecutor(registry, AgentContext())
        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        # All should complete
        assert all(t.status == TaskStatus.COMPLETED for t in result.tasks)


# ===========================================================================
# 4. Agent Health Monitor Tests
# ===========================================================================

class TestAgentMetrics:
    """Test AgentMetrics dataclass."""

    def test_metrics_defaults(self):
        m = AgentMetrics(agent_id="test")
        assert m.request_count == 0
        assert m.error_count == 0
        assert m.avg_latency_ms == 0.0
        assert m.error_rate == 0.0
        assert m.healthy is True

    def test_avg_latency(self):
        m = AgentMetrics(agent_id="t")
        m.request_count = 3
        m.total_latency_ms = 300.0
        assert m.avg_latency_ms == 100.0

    def test_error_rate(self):
        m = AgentMetrics(agent_id="t")
        m.request_count = 10
        m.error_count = 2
        assert m.error_rate == 0.2

    def test_to_dict(self):
        m = AgentMetrics(agent_id="t", request_count=5, error_count=1,
                         total_latency_ms=250.0)
        d = m.to_dict()
        assert d["agent_id"] == "t"
        assert d["request_count"] == 5
        assert d["error_count"] == 1
        assert d["avg_latency_ms"] == 50.0
        assert d["error_rate"] == 0.2


class TestAgentHealthMonitor:
    """Test AgentHealthMonitor health check and metrics."""

    def setup_method(self):
        self.registry = AgentRegistry()
        self.monitor = AgentHealthMonitor(self.registry)

    def test_record_request_success(self):
        self.monitor.record_request("agent_a", 50.0, success=True)
        m = self.monitor.get_metrics("agent_a")
        assert m["request_count"] == 1
        assert m["avg_latency_ms"] == 50.0

    def test_record_request_failure(self):
        self.monitor.record_request("agent_b", 100.0, success=False)
        m = self.monitor.get_metrics("agent_b")
        assert m["error_count"] == 1
        assert m["error_rate"] == 1.0

    def test_record_multiple_requests(self):
        self.monitor.record_request("agent_c", 50.0, True)
        self.monitor.record_request("agent_c", 150.0, True)
        self.monitor.record_request("agent_c", 100.0, False)
        m = self.monitor.get_metrics("agent_c")
        assert m["request_count"] == 3
        assert m["error_count"] == 1
        assert m["avg_latency_ms"] == 100.0

    def test_get_metrics_unknown_agent(self):
        m = self.monitor.get_metrics("unknown")
        assert m["request_count"] == 0

    def test_get_all_metrics(self):
        self.monitor.record_request("a1", 10.0, True)
        self.monitor.record_request("a2", 20.0, True)
        all_m = self.monitor.get_metrics()
        assert "a1" in all_m
        assert "a2" in all_m

    @pytest.mark.asyncio
    async def test_check_agent_health_success(self):
        echo = EchoAgent(agent_id="health_echo")
        self.registry.register(echo)

        result = await self.monitor.check_agent_health("health_echo")
        assert result["healthy"] is True
        assert result["agent_id"] == "health_echo"
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_check_agent_health_not_found(self):
        result = await self.monitor.check_agent_health("nonexistent")
        assert result["healthy"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_check_agent_health_error_state(self):
        echo = EchoAgent(agent_id="error_agent")
        echo.status = AgentStatus.ERROR
        self.registry.register(echo)

        result = await self.monitor.check_agent_health("error_agent")
        assert result["healthy"] is False
        assert "error" in result["status"]

    @pytest.mark.asyncio
    async def test_check_agent_health_stopped_state(self):
        echo = EchoAgent(agent_id="stopped_agent")
        echo.status = AgentStatus.STOPPED
        self.registry.register(echo)

        result = await self.monitor.check_agent_health("stopped_agent")
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_check_agent_health_timeout(self):
        slow = SlowAgent(delay=5.0, agent_id="slow_health")
        self.registry.register(slow)

        monitor = AgentHealthMonitor(self.registry, health_timeout=0.1)
        result = await monitor.check_agent_health("slow_health")
        assert result["healthy"] is False
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_check_all_health(self):
        self.registry.register(EchoAgent(agent_id="h1"))
        self.registry.register(EchoAgent(agent_id="h2"))

        result = await self.monitor.check_all_health()
        assert result["total"] == 2
        assert result["healthy"] == 2
        assert result["unhealthy"] == 0
        assert len(result["agents"]) == 2

    @pytest.mark.asyncio
    async def test_check_all_health_mixed(self):
        self.registry.register(EchoAgent(agent_id="ok"))
        fail = FailAgent(agent_id="bad")
        self.registry.register(fail)

        result = await self.monitor.check_all_health()
        assert result["total"] == 2
        assert result["healthy"] == 1
        assert result["unhealthy"] == 1

    def test_get_platform_health(self):
        self.registry.register(EchoAgent(agent_id="p1"))
        self.registry.register(EchoAgent(agent_id="p2"))
        self.monitor.record_request("p1", 10.0, True)
        self.monitor.record_request("p1", 20.0, False)

        health = self.monitor.get_platform_health()
        assert health["total_agents"] == 2
        assert health["total_requests"] == 2
        assert health["total_errors"] == 1
        assert health["overall_error_rate"] == 0.5

    def test_platform_health_no_requests(self):
        self.registry.register(EchoAgent(agent_id="idle"))
        health = self.monitor.get_platform_health()
        assert health["overall_error_rate"] == 0.0


# ===========================================================================
# 5. Skill→Agent Bridge Tests
# ===========================================================================

class TestSkillAgentBridge:
    """Test BaseSkill.call_agent() bridge to multi-agent layer."""

    def setup_method(self):
        self.registry = AgentRegistry()

    @pytest.mark.asyncio
    async def test_call_agent_success(self):
        echo = EchoAgent(agent_id="bridge_echo")
        self.registry.register(echo)

        skill = BridgeTestSkill()
        result = await skill.run({
            "_registry": self.registry,
            "agent_id": "bridge_echo",
            "action": "test",
            "data": "skill_data",
        })
        assert result.success is True
        assert "echo" in result.data
        assert "call_agent" in result.steps_completed

    @pytest.mark.asyncio
    async def test_call_agent_not_found(self):
        skill = BridgeTestSkill()
        result = await skill.run({
            "_registry": self.registry,
            "agent_id": "nonexistent",
            "action": "test",
        })
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_call_agent_timeout(self):
        slow = SlowAgent(delay=5.0, agent_id="slow_bridge")
        self.registry.register(slow)

        skill = BridgeTestSkill()
        result = await skill.run({
            "_registry": self.registry,
            "agent_id": "slow_bridge",
            "action": "slow_task",
            "timeout": 0.1,
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_call_agent_error_response(self):
        fail = FailAgent(agent_id="fail_bridge")
        self.registry.register(fail)

        skill = BridgeTestSkill()
        result = await skill.run({
            "_registry": self.registry,
            "agent_id": "fail_bridge",
            "action": "fail",
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_call_agent_no_registry_raises(self):
        """Without registry and outside web context, should fail."""
        skill = BridgeTestSkill()
        # Don't pass registry — should raise ValueError
        result = await skill.run({
            "agent_id": "any",
            "action": "test",
        })
        assert result.success is False


# ===========================================================================
# 6. E2E Multi-Agent Collaboration Scenarios
# ===========================================================================

class TestE2EMultiAgentScenarios:
    """End-to-end multi-agent collaboration scenarios."""

    @pytest.mark.asyncio
    async def test_fan_out_fan_in_with_health_check(self):
        """Fan-out/fan-in execution with health monitoring."""
        registry = AgentRegistry()
        bus = MessageBus()
        context = AgentContext(context_id="e2e_fan")

        e1 = EchoAgent(agent_id="worker_1")
        e2 = EchoAgent(agent_id="worker_2")
        agg = EchoAgent(agent_id="aggregator")
        registry.register(e1)
        registry.register(e2)
        registry.register(agg)
        registry.connect_bus(bus)

        # Health check before execution
        monitor = AgentHealthMonitor(registry)
        health = await monitor.check_all_health()
        assert health["healthy"] == 3

        # Execute fan-out/fan-in plan
        executor = MultiAgentExecutor(registry, context)
        plan = executor.build_fan_out_fan_in_plan(
            "parallel workers → aggregator",
            [
                {"agent_id": "worker_1", "action": "process_a"},
                {"agent_id": "worker_2", "action": "process_b"},
            ],
            {"agent_id": "aggregator", "action": "merge"},
        )
        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        assert all(t.status == TaskStatus.COMPLETED for t in result.tasks)

        # Record metrics
        for task in result.tasks:
            monitor.record_request(task.agent_id, task.duration * 1000, True)

        # Verify metrics
        metrics = monitor.get_metrics()
        assert len(metrics) == 3
        platform = monitor.get_platform_health()
        assert platform["total_requests"] == 3
        assert platform["total_errors"] == 0

    @pytest.mark.asyncio
    async def test_sequential_with_failure_recovery(self):
        """Sequential plan where first task fails, blocking second."""
        registry = AgentRegistry()
        context = AgentContext()

        fail = FailAgent(agent_id="fail_step")
        echo = EchoAgent(agent_id="dependent_step")
        registry.register(fail)
        registry.register(echo)

        executor = MultiAgentExecutor(registry, context)
        plan = executor.build_sequential_plan(
            "failure recovery",
            [
                {"agent_id": "fail_step", "action": "break"},
                {"agent_id": "dependent_step", "action": "continue"},
            ],
        )
        # Set low retries for speed
        plan.tasks[0].max_retries = 0

        result = await executor.execute(plan)
        assert result.status == TaskStatus.FAILED
        assert result.tasks[0].status == TaskStatus.FAILED
        assert result.tasks[1].status == TaskStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_timeout_cascade(self):
        """Timeout on first task cascades to skip dependent tasks."""
        registry = AgentRegistry()
        context = AgentContext()

        slow = SlowAgent(delay=5.0, agent_id="slow_first")
        echo = EchoAgent(agent_id="waiting_second")
        registry.register(slow)
        registry.register(echo)

        executor = MultiAgentExecutor(registry, context)
        plan = ExecutionPlan(objective="timeout cascade")
        plan.add_task(ExecutionTask(
            id="slow", agent_id="slow_first", action="slow",
            timeout_sec=0.1, max_retries=0,
        ))
        plan.add_task(ExecutionTask(
            id="fast", agent_id="waiting_second", action="test",
            dependencies=["slow"],
        ))

        result = await executor.execute(plan)
        assert result.status == TaskStatus.FAILED
        assert result.tasks[0].status == TaskStatus.FAILED
        assert result.tasks[1].status == TaskStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_cancel_during_execution(self):
        """Cancel a plan that has pending tasks."""
        registry = AgentRegistry()
        context = AgentContext()
        echo = EchoAgent(agent_id="cancel_target")
        registry.register(echo)

        executor = MultiAgentExecutor(registry, context)
        plan = executor.build_sequential_plan(
            "cancel during exec",
            [
                {"agent_id": "cancel_target", "action": "step1"},
                {"agent_id": "cancel_target", "action": "step2"},
                {"agent_id": "cancel_target", "action": "step3"},
            ],
        )
        cancelled = executor.cancel_plan(plan)
        assert cancelled.status == TaskStatus.FAILED
        assert all(t.status == TaskStatus.SKIPPED for t in cancelled.tasks)

    @pytest.mark.asyncio
    async def test_skill_agent_collaboration(self):
        """Skill invokes Agent via call_agent during workflow execution."""
        registry = AgentRegistry()
        echo = EchoAgent(agent_id="skill_target")
        registry.register(echo)

        skill = BridgeTestSkill()
        result = await skill.run({
            "_registry": registry,
            "agent_id": "skill_target",
            "action": "skill_delegated",
            "data": "from_skill",
        })
        assert result.success is True
        assert result.data["echo"]["action"] == "skill_delegated"

    @pytest.mark.asyncio
    async def test_health_monitor_after_execution(self):
        """Health monitor reflects state after successful execution."""
        registry = AgentRegistry()
        context = AgentContext()

        echo = EchoAgent(agent_id="post_exec")
        registry.register(echo)

        monitor = AgentHealthMonitor(registry)

        # Before execution
        pre_health = await monitor.check_agent_health("post_exec")
        assert pre_health["healthy"] is True

        # Execute a plan
        executor = MultiAgentExecutor(registry, context)
        plan = executor.build_sequential_plan(
            "health check after",
            [{"agent_id": "post_exec", "action": "work"}],
        )
        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED

        # Record execution metrics
        for task in result.tasks:
            monitor.record_request(task.agent_id, task.duration * 1000, True)

        # After execution, health check still passes
        post_health = await monitor.check_agent_health("post_exec")
        assert post_health["healthy"] is True

        # Metrics reflect the execution
        m = monitor.get_metrics("post_exec")
        assert m["request_count"] == 1

    @pytest.mark.asyncio
    async def test_multi_agent_bus_health_execution_integration(self):
        """Full integration: bus + registry + executor + health monitor."""
        # Setup infrastructure
        registry = AgentRegistry()
        bus = MessageBus()
        context = AgentContext(context_id="full_integration")
        registry.connect_bus(bus)

        # Register agents
        counter = CounterAgent(agent_id="integr_counter")
        echo = EchoAgent(agent_id="integr_echo")
        registry.register(counter)
        registry.register(echo)

        # Health check
        monitor = AgentHealthMonitor(registry)
        health = await monitor.check_all_health()
        assert health["total"] == 2
        assert health["healthy"] == 2

        # Direct message via bus
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="integr_echo",
            content={"ping": True},
        )
        resp = await bus.send(msg)
        assert resp.content["echo"]["ping"] is True

        # Execute DAG plan
        executor = MultiAgentExecutor(registry, context)
        plan = executor.build_parallel_plan(
            "integration test",
            [
                {"agent_id": "integr_counter", "action": "count"},
                {"agent_id": "integr_echo", "action": "echo"},
            ],
        )
        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED

        # Counter was invoked
        assert counter.call_count >= 1

        # Context has trace
        trace = context.get_trace()
        assert len(trace) > 0

        # Bus has history
        history = bus.get_history()
        assert len(history) > 0

        # Platform health
        monitor.record_request("integr_counter", 10.0, True)
        monitor.record_request("integr_echo", 5.0, True)
        platform = monitor.get_platform_health()
        assert platform["total_agents"] == 2
        assert platform["total_requests"] == 2
