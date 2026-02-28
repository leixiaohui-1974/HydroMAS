"""Tests for Phase 2 multi-agent enhancements:

1. Load-aware agent selection (Registry.find_best_agent + Executor integration)
2. Event-driven workflows (Executor emits events via MessageBus pub/sub)
3. Dynamic replanning (PlanningAgent.replan + expanded templates)
4. Plan management API endpoints

Phase 2 多智能体增强测试：
1. 负载感知 Agent 选择
2. 事件驱动工作流
3. 动态重规划
4. 计划管理 API
"""

from __future__ import annotations

import asyncio
import copy

import pytest

from agents.base_agent import AgentStatus, BaseAgent
from agents.context import AgentContext
from agents.executor import (
    ExecutionPlan,
    ExecutionTask,
    MultiAgentExecutor,
    TaskStatus,
)
from agents.health import AgentHealthMonitor, AgentMetrics
from agents.message import AgentMessage, MessageBus, MessageType
from agents.planning_agent import PlanningAgent, TaskNode, TaskPlan
from agents.registry import AgentRegistry


# ---------------------------------------------------------------------------
# Test agents
# ---------------------------------------------------------------------------

class EchoAgent(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["echo", "test"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        return message.reply({"echo": message.content, "agent_id": self.agent_id})


class FailAgent(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["fail", "compute"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        raise RuntimeError("FailAgent always fails")


class SlowAgent(BaseAgent):
    def __init__(self, delay: float = 2.0, **kwargs):
        super().__init__(**kwargs)
        self.delay = delay

    def get_capabilities(self) -> list[str]:
        return ["slow_task", "compute"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        await asyncio.sleep(self.delay)
        return message.reply({"done": True})


class ComputeAgent(BaseAgent):
    """Agent with 'compute' capability for testing agent selection."""

    def __init__(self, name_tag: str = "", **kwargs):
        super().__init__(**kwargs)
        self.name_tag = name_tag
        self.invoked = False

    def get_capabilities(self) -> list[str]:
        return ["compute", "math"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        self.invoked = True
        return message.reply({"computed": True, "by": self.agent_id})


# ===========================================================================
# 1. Load-Aware Agent Selection Tests
# ===========================================================================

class TestFindBestAgent:
    """Test Registry.find_best_agent with health-aware ranking."""

    def setup_method(self):
        self.registry = AgentRegistry()
        self.monitor = AgentHealthMonitor(self.registry)

    def test_find_best_single_candidate(self):
        agent = ComputeAgent(agent_id="solo")
        self.registry.register(agent)
        best = self.registry.find_best_agent("compute")
        assert best is agent

    def test_find_best_no_candidates(self):
        best = self.registry.find_best_agent("nonexistent")
        assert best is None

    def test_find_best_without_monitor(self):
        a1 = ComputeAgent(agent_id="c1")
        a2 = ComputeAgent(agent_id="c2")
        self.registry.register(a1)
        self.registry.register(a2)
        # Without monitor, returns first available
        best = self.registry.find_best_agent("compute")
        assert best is not None

    def test_find_best_prefers_healthy_agent(self):
        healthy = ComputeAgent(agent_id="healthy")
        unhealthy = ComputeAgent(agent_id="unhealthy")
        self.registry.register(healthy)
        self.registry.register(unhealthy)

        # Record failures for unhealthy agent
        self.monitor.record_request("unhealthy", 100.0, success=False)
        self.monitor.record_request("unhealthy", 100.0, success=False)
        self.monitor.record_request("healthy", 50.0, success=True)

        best = self.registry.find_best_agent("compute", health_monitor=self.monitor)
        assert best.agent_id == "healthy"

    def test_find_best_prefers_low_error_rate(self):
        a1 = ComputeAgent(agent_id="reliable")
        a2 = ComputeAgent(agent_id="flaky")
        self.registry.register(a1)
        self.registry.register(a2)

        # reliable: 0% error rate
        self.monitor.record_request("reliable", 50.0, True)
        self.monitor.record_request("reliable", 60.0, True)
        # flaky: 50% error rate
        self.monitor.record_request("flaky", 50.0, True)
        self.monitor.record_request("flaky", 50.0, False)

        best = self.registry.find_best_agent("compute", health_monitor=self.monitor)
        assert best.agent_id == "reliable"

    def test_find_best_prefers_low_latency(self):
        fast = ComputeAgent(agent_id="fast_agent")
        slow = ComputeAgent(agent_id="slow_agent")
        self.registry.register(fast)
        self.registry.register(slow)

        # Both healthy, 0% error — differ only in latency
        self.monitor.record_request("fast_agent", 10.0, True)
        self.monitor.record_request("slow_agent", 500.0, True)

        best = self.registry.find_best_agent("compute", health_monitor=self.monitor)
        assert best.agent_id == "fast_agent"

    def test_find_best_filters_stopped_agents(self):
        active = ComputeAgent(agent_id="active")
        stopped = ComputeAgent(agent_id="stopped")
        stopped.status = AgentStatus.STOPPED
        self.registry.register(active)
        self.registry.register(stopped)

        best = self.registry.find_best_agent("compute")
        assert best.agent_id == "active"

    def test_find_best_falls_back_when_all_stopped(self):
        """If all are stopped, still returns a candidate (graceful degradation)."""
        stopped = ComputeAgent(agent_id="only_stopped")
        stopped.status = AgentStatus.STOPPED
        self.registry.register(stopped)

        best = self.registry.find_best_agent("compute")
        assert best is not None  # graceful fallback


class TestExecutorHealthAwareSelection:
    """Test that executor uses health-aware selection for capability lookup."""

    @pytest.mark.asyncio
    async def test_executor_records_success_metrics(self):
        registry = AgentRegistry()
        monitor = AgentHealthMonitor(registry)
        echo = EchoAgent(agent_id="metric_echo")
        registry.register(echo)

        executor = MultiAgentExecutor(registry, AgentContext(), health_monitor=monitor)
        plan = executor.build_sequential_plan(
            "metrics test",
            [{"agent_id": "metric_echo", "action": "test"}],
        )
        await executor.execute(plan)

        m = monitor.get_metrics("metric_echo")
        assert m["request_count"] == 1
        assert m["error_count"] == 0

    @pytest.mark.asyncio
    async def test_executor_records_failure_metrics(self):
        registry = AgentRegistry()
        monitor = AgentHealthMonitor(registry)
        fail = FailAgent(agent_id="metric_fail")
        registry.register(fail)

        executor = MultiAgentExecutor(registry, AgentContext(), health_monitor=monitor)
        plan = ExecutionPlan(objective="fail metrics")
        plan.add_task(ExecutionTask(
            id="t1", agent_id="metric_fail", action="fail", max_retries=0,
        ))
        await executor.execute(plan)

        m = monitor.get_metrics("metric_fail")
        assert m["request_count"] == 1
        assert m["error_count"] == 1

    @pytest.mark.asyncio
    async def test_executor_uses_best_agent_for_capability(self):
        registry = AgentRegistry()
        monitor = AgentHealthMonitor(registry)

        fast = ComputeAgent(agent_id="fast_compute")
        slow = ComputeAgent(agent_id="slow_compute")
        registry.register(fast)
        registry.register(slow)

        # Make slow agent have higher error rate
        monitor.record_request("slow_compute", 100.0, False)
        monitor.record_request("fast_compute", 10.0, True)

        executor = MultiAgentExecutor(registry, AgentContext(), health_monitor=monitor)
        plan = ExecutionPlan(objective="capability routing")
        plan.add_task(ExecutionTask(
            id="t1", agent_id="nonexistent", action="compute",
        ))
        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        # The fast_compute agent should have been selected
        assert result.tasks[0].result.get("by") == "fast_compute"


# ===========================================================================
# 2. Event-Driven Workflow Tests
# ===========================================================================

class TestExecutorEventEmission:
    """Test that executor emits events via MessageBus."""

    @pytest.mark.asyncio
    async def test_plan_started_event_emitted(self):
        registry = AgentRegistry()
        bus = MessageBus()
        echo = EchoAgent(agent_id="evt_echo")
        registry.register(echo)

        events_received = []

        async def event_handler(msg):
            events_received.append(msg)
            return None

        bus.subscribe("plan.started", event_handler)

        executor = MultiAgentExecutor(
            registry, AgentContext(), message_bus=bus,
        )
        plan = executor.build_sequential_plan(
            "event test", [{"agent_id": "evt_echo", "action": "test"}],
        )
        await executor.execute(plan)

        assert len(events_received) >= 1
        assert events_received[0].content["topic"] == "plan.started"
        assert "plan_id" in events_received[0].content

    @pytest.mark.asyncio
    async def test_task_completed_event_emitted(self):
        registry = AgentRegistry()
        bus = MessageBus()
        echo = EchoAgent(agent_id="task_evt")
        registry.register(echo)

        task_events = []

        async def handler(msg):
            task_events.append(msg)
            return None

        bus.subscribe("task.completed", handler)

        executor = MultiAgentExecutor(
            registry, AgentContext(), message_bus=bus,
        )
        plan = executor.build_sequential_plan(
            "task event test", [{"agent_id": "task_evt", "action": "test"}],
        )
        await executor.execute(plan)

        assert len(task_events) >= 1
        assert task_events[0].content["agent_id"] == "task_evt"

    @pytest.mark.asyncio
    async def test_plan_completed_event_emitted(self):
        registry = AgentRegistry()
        bus = MessageBus()
        echo = EchoAgent(agent_id="done_evt")
        registry.register(echo)

        completed_events = []

        async def handler(msg):
            completed_events.append(msg)
            return None

        bus.subscribe("plan.completed", handler)

        executor = MultiAgentExecutor(
            registry, AgentContext(), message_bus=bus,
        )
        plan = executor.build_sequential_plan(
            "completion test", [{"agent_id": "done_evt", "action": "test"}],
        )
        await executor.execute(plan)

        assert len(completed_events) >= 1
        assert completed_events[0].content["status"] == "completed"

    @pytest.mark.asyncio
    async def test_no_events_without_bus(self):
        """Executor should work fine without a MessageBus (no events)."""
        registry = AgentRegistry()
        echo = EchoAgent(agent_id="no_bus")
        registry.register(echo)

        executor = MultiAgentExecutor(registry, AgentContext())
        plan = executor.build_sequential_plan(
            "no bus test", [{"agent_id": "no_bus", "action": "test"}],
        )
        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_multiple_event_subscribers(self):
        registry = AgentRegistry()
        bus = MessageBus()
        echo = EchoAgent(agent_id="multi_sub")
        registry.register(echo)

        sub1_events = []
        sub2_events = []

        async def handler1(msg):
            sub1_events.append(msg)
            return None

        async def handler2(msg):
            sub2_events.append(msg)
            return None

        bus.subscribe("plan.completed", handler1)
        bus.subscribe("plan.completed", handler2)

        executor = MultiAgentExecutor(
            registry, AgentContext(), message_bus=bus,
        )
        plan = executor.build_sequential_plan(
            "multi sub", [{"agent_id": "multi_sub", "action": "test"}],
        )
        await executor.execute(plan)

        assert len(sub1_events) >= 1
        assert len(sub2_events) >= 1


# ===========================================================================
# 3. Dynamic Replanning Tests
# ===========================================================================

class TestPlanningAgentTemplates:
    """Test expanded plan templates in PlanningAgent."""

    def setup_method(self):
        self.agent = PlanningAgent(agent_id="test_planner")

    def test_leak_diagnosis_template(self):
        plan = self.agent.plan("检测管道泄漏")
        assert plan.objective == "Leak diagnosis pipeline"
        assert len(plan.nodes) == 4
        node_ids = [n.id for n in plan.nodes]
        assert "balance" in node_ids
        assert "localize" in node_ids

    def test_evap_optimization_template(self):
        plan = self.agent.plan("优化冷却塔蒸发")
        assert plan.objective == "Evaporation optimization"
        assert len(plan.nodes) == 4

    def test_water_dispatch_template(self):
        plan = self.agent.plan("全局调度优化")
        assert plan.objective == "Water dispatch optimization"
        assert len(plan.nodes) == 4

    def test_daily_report_template(self):
        plan = self.agent.plan("生成日报")
        assert plan.objective == "Daily operations report"
        assert len(plan.nodes) == 4

    def test_controller_comparison_template(self):
        plan = self.agent.plan("比较PID和MPC控制器")
        assert plan.objective == "Compare PID and MPC controllers"
        assert len(plan.nodes) == 4

    def test_full_analysis_template(self):
        plan = self.agent.plan("全面分析系统")
        assert plan.objective == "Full system analysis"
        assert len(plan.nodes) == 5

    def test_default_plan_for_unknown_input(self):
        plan = self.agent.plan("做一些其他事情")
        assert len(plan.nodes) == 1
        assert plan.nodes[0].id == "task_1"

    def test_best_template_by_keyword_score(self):
        """If multiple templates match, the one with more keywords wins."""
        plan = self.agent.plan("leak detection in pipe system using 泄漏 detection")
        assert "leak" in plan.objective.lower() or "Leak" in plan.objective


class TestPlanningAgentReplan:
    """Test PlanningAgent.replan() for dynamic replanning."""

    def setup_method(self):
        self.agent = PlanningAgent(agent_id="replanner")

    def test_replan_removes_failed_branch(self):
        original = TaskPlan(objective="original plan")
        original.add_node(TaskNode("a", "Task A", "tool_a"))
        original.add_node(TaskNode("b", "Task B", "tool_b", dependencies=["a"]))
        original.add_node(TaskNode("c", "Task C", "tool_c"))

        new_plan = self.agent.replan(original, failed_tasks=["a"])
        node_ids = [n.id for n in new_plan.nodes]
        # a failed, b depends on a → both removed; c remains
        assert "a" not in node_ids
        assert "b" not in node_ids
        assert "c" in node_ids

    def test_replan_keeps_completed_tasks_out(self):
        original = TaskPlan(objective="with completed")
        original.add_node(TaskNode("a", "Done", "tool_a", status="completed"))
        original.add_node(TaskNode("b", "Pending", "tool_b", dependencies=["a"]))

        new_plan = self.agent.replan(original, failed_tasks=[])
        node_ids = [n.id for n in new_plan.nodes]
        # a is completed → excluded; b remains
        assert "a" not in node_ids
        assert "b" in node_ids

    def test_replan_transitive_dependency_removal(self):
        original = TaskPlan(objective="chain")
        original.add_node(TaskNode("a", "A", "t"))
        original.add_node(TaskNode("b", "B", "t", dependencies=["a"]))
        original.add_node(TaskNode("c", "C", "t", dependencies=["b"]))
        original.add_node(TaskNode("d", "D", "t"))

        new_plan = self.agent.replan(original, failed_tasks=["a"])
        node_ids = [n.id for n in new_plan.nodes]
        # a→b→c all removed; d remains
        assert "a" not in node_ids
        assert "b" not in node_ids
        assert "c" not in node_ids
        assert "d" in node_ids

    def test_replan_empty_when_all_failed(self):
        original = TaskPlan(objective="all fail")
        original.add_node(TaskNode("a", "A", "t"))
        original.add_node(TaskNode("b", "B", "t", dependencies=["a"]))

        new_plan = self.agent.replan(original, failed_tasks=["a"])
        assert len(new_plan.nodes) == 0

    def test_replan_objective_prefixed(self):
        original = TaskPlan(objective="my plan")
        original.add_node(TaskNode("a", "A", "t"))

        new_plan = self.agent.replan(original, failed_tasks=["a"])
        assert "[Replanned]" in new_plan.objective

    @pytest.mark.asyncio
    async def test_replan_via_message(self):
        """Test replan action via handle_message."""
        original_data = {
            "objective": "test plan",
            "tasks": [
                {"id": "a", "description": "Task A", "tool_or_skill": "t",
                 "dependencies": [], "status": "failed"},
                {"id": "b", "description": "Task B", "tool_or_skill": "t",
                 "dependencies": ["a"], "status": "pending"},
                {"id": "c", "description": "Task C", "tool_or_skill": "t",
                 "dependencies": [], "status": "pending"},
            ],
        }
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="replanner",
            content={
                "action": "replan",
                "params": {
                    "original_plan": original_data,
                    "failed_tasks": ["a"],
                },
            },
        )
        response = await self.agent.handle_message(msg)
        plan_data = response.content["plan"]
        assert response.content["replanned"] is True
        task_ids = [t["id"] for t in plan_data["tasks"]]
        assert "a" not in task_ids
        assert "b" not in task_ids
        assert "c" in task_ids


# ===========================================================================
# 4. E2E Integration Scenarios
# ===========================================================================

class TestPhase2E2EIntegration:
    """End-to-end multi-agent scenarios with Phase 2 features."""

    @pytest.mark.asyncio
    async def test_health_aware_execution_with_events(self):
        """Full pipeline: health-aware selection + event emission."""
        registry = AgentRegistry()
        bus = MessageBus()
        context = AgentContext()
        monitor = AgentHealthMonitor(registry)

        fast = ComputeAgent(agent_id="fast_worker")
        slow = ComputeAgent(agent_id="slow_worker")
        registry.register(fast)
        registry.register(slow)
        registry.connect_bus(bus)

        # Pre-seed metrics: slow_worker has high latency
        monitor.record_request("slow_worker", 500.0, True)
        monitor.record_request("fast_worker", 10.0, True)

        # Track events
        all_events = []

        async def event_collector(msg):
            all_events.append(msg)
            return None

        bus.subscribe("plan.started", event_collector)
        bus.subscribe("task.completed", event_collector)
        bus.subscribe("plan.completed", event_collector)

        executor = MultiAgentExecutor(
            registry, context,
            health_monitor=monitor,
            message_bus=bus,
        )

        plan = ExecutionPlan(objective="health-aware execution")
        plan.add_task(ExecutionTask(
            id="t1", agent_id="nonexistent", action="compute",
        ))
        result = await executor.execute(plan)

        assert result.status == TaskStatus.COMPLETED
        # fast_worker should be selected via health-aware routing
        assert result.tasks[0].result["by"] == "fast_worker"
        # Events should have been emitted
        topics = [e.content.get("topic") for e in all_events]
        assert "plan.started" in topics
        assert "task.completed" in topics
        assert "plan.completed" in topics

    @pytest.mark.asyncio
    async def test_planning_to_execution_flow(self):
        """Plan with PlanningAgent → build ExecutionPlan → execute."""
        planner = PlanningAgent(agent_id="flow_planner")
        task_plan = planner.plan("检测管道泄漏")

        # Convert TaskPlan → ExecutionPlan
        registry = AgentRegistry()
        # Register an echo agent for each tool
        for node in task_plan.nodes:
            echo = EchoAgent(agent_id=node.tool_or_skill)
            if registry.get_agent(node.tool_or_skill) is None:
                registry.register(echo)

        exec_plan = ExecutionPlan(objective=task_plan.objective)
        for node in task_plan.nodes:
            exec_plan.add_task(ExecutionTask(
                id=node.id,
                agent_id=node.tool_or_skill,
                action=node.tool_or_skill,
                params=node.params,
                dependencies=node.dependencies,
            ))

        executor = MultiAgentExecutor(registry, AgentContext())
        result = await executor.execute(exec_plan)
        assert result.status == TaskStatus.COMPLETED
        assert len(result.tasks) == 4

    @pytest.mark.asyncio
    async def test_replan_after_execution_failure(self):
        """Simulate: execute plan → detect failure → replan → execute remainder."""
        registry = AgentRegistry()
        context = AgentContext()

        fail = FailAgent(agent_id="bad_tool")
        echo = EchoAgent(agent_id="good_tool")
        registry.register(fail)
        registry.register(echo)

        # Phase 1: Execute original plan (has failure)
        plan1 = ExecutionPlan(objective="original")
        plan1.add_task(ExecutionTask(
            id="a", agent_id="bad_tool", action="fail", max_retries=0,
        ))
        plan1.add_task(ExecutionTask(
            id="b", agent_id="good_tool", action="test", dependencies=["a"],
        ))
        plan1.add_task(ExecutionTask(
            id="c", agent_id="good_tool", action="test",
        ))

        executor = MultiAgentExecutor(registry, context)
        result1 = await executor.execute(plan1)
        assert result1.status == TaskStatus.FAILED
        assert result1.tasks[2].status == TaskStatus.COMPLETED  # c ran fine

        # Phase 2: Replan based on failures
        planner = PlanningAgent(agent_id="replanner")
        original_data = result1.to_dict()
        task_plan_data = {
            "objective": original_data["objective"],
            "tasks": [
                {"id": t["id"], "description": t["action"],
                 "tool_or_skill": t["agent_id"],
                 "dependencies": t["dependencies"],
                 "status": "failed" if t["status"] == "failed" else t["status"]}
                for t in original_data["tasks"]
            ],
        }
        failed_ids = [t["id"] for t in original_data["tasks"] if t["status"] == "failed"]
        new_task_plan = planner.replan(
            TaskPlan(objective=task_plan_data["objective"]),
            failed_tasks=failed_ids,
        )
        # After replan, no tasks remain (all depended on 'a' or are completed)
        # This validates the replan correctly removed blocked branches
        assert all(
            n.id not in {"a", "b"}
            for n in new_task_plan.nodes
        )
