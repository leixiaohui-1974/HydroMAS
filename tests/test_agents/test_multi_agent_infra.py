"""Tests for multi-agent infrastructure: BaseAgent, Message, MessageBus,
AgentRegistry, AgentContext, and MultiAgentExecutor.

多智能体基础设施测试：BaseAgent、消息、消息总线、Agent注册表、Agent上下文、多Agent执行器。
"""

from __future__ import annotations

import asyncio
import pytest

from agents.base_agent import AgentCard, AgentStatus, BaseAgent
from agents.context import AgentContext, TraceEntry
from agents.executor import (
    ExecutionPlan,
    ExecutionTask,
    MultiAgentExecutor,
    TaskStatus,
)
from agents.message import (
    AgentMessage,
    MessageBus,
    MessagePriority,
    MessageType,
)
from agents.registry import AgentRegistry


# ---------------------------------------------------------------------------
# Concrete test agent (implements BaseAgent)
# ---------------------------------------------------------------------------

class EchoAgent(BaseAgent):
    """Simple test agent that echoes back the message content."""

    def get_capabilities(self) -> list[str]:
        return ["echo", "test"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        return message.reply({"echo": message.content, "agent_id": self.agent_id})


class FailAgent(BaseAgent):
    """Agent that always fails."""

    def get_capabilities(self) -> list[str]:
        return ["fail"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        raise RuntimeError("FailAgent always fails")


class AdderAgent(BaseAgent):
    """Agent that adds numbers from params."""

    def get_capabilities(self) -> list[str]:
        return ["add", "math"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        params = message.content.get("params", {})
        a = params.get("a", 0)
        b = params.get("b", 0)
        return message.reply({"sum": a + b})


# ===========================================================================
# Test BaseAgent
# ===========================================================================

class TestBaseAgent:
    def test_agent_creation(self):
        agent = EchoAgent(agent_id="test_echo")
        assert agent.agent_id == "test_echo"
        assert agent.status == AgentStatus.IDLE
        assert agent.get_capabilities() == ["echo", "test"]

    def test_agent_auto_id(self):
        agent = EchoAgent()
        assert agent.agent_id.startswith("EchoAgent_")

    def test_agent_repr(self):
        agent = EchoAgent(agent_id="e1")
        assert "EchoAgent" in repr(agent)
        assert "e1" in repr(agent)

    @pytest.mark.asyncio
    async def test_agent_lifecycle(self):
        agent = EchoAgent(agent_id="lifecycle_test")
        await agent.initialize()
        assert agent.status == AgentStatus.IDLE
        await agent.shutdown()
        assert agent.status == AgentStatus.STOPPED

    @pytest.mark.asyncio
    async def test_handle_message(self):
        agent = EchoAgent(agent_id="echo_1")
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="tester",
            recipient="echo_1",
            content={"hello": "world"},
        )
        response = await agent.handle_message(msg)
        assert response.type == MessageType.RESPONSE
        assert response.content["echo"] == {"hello": "world"}
        assert response.content["agent_id"] == "echo_1"

    def test_agent_card(self):
        card = AgentCard(
            name="TestAgent",
            display_name="Test",
            capabilities=["a", "b"],
        )
        agent = EchoAgent(agent_id="card_test", card=card)
        assert agent.get_card() is not None
        assert agent.get_card().name == "TestAgent"
        d = card.to_dict()
        assert d["name"] == "TestAgent"
        assert d["capabilities"] == ["a", "b"]


# ===========================================================================
# Test AgentMessage
# ===========================================================================

class TestAgentMessage:
    def test_message_creation(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="a",
            recipient="b",
            content={"key": "value"},
        )
        assert msg.type == MessageType.REQUEST
        assert msg.sender == "a"
        assert msg.recipient == "b"
        assert msg.content == {"key": "value"}
        assert len(msg.id) == 12

    def test_message_reply(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="a",
            recipient="b",
            content={"q": "hello"},
        )
        reply = msg.reply({"answer": "world"})
        assert reply.type == MessageType.RESPONSE
        assert reply.sender == "b"
        assert reply.recipient == "a"
        assert reply.correlation_id == msg.id
        assert reply.content == {"answer": "world"}

    def test_error_reply(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="a",
            recipient="b",
        )
        err = msg.error_reply("something broke")
        assert err.type == MessageType.ERROR
        assert err.content["error"] == "something broke"
        assert err.correlation_id == msg.id

    def test_message_to_dict(self):
        msg = AgentMessage(
            type=MessageType.EVENT,
            sender="publisher",
            content={"event": "alarm"},
        )
        d = msg.to_dict()
        assert d["type"] == "event"
        assert d["sender"] == "publisher"
        assert "timestamp" in d

    def test_message_priority(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="a",
            priority=MessagePriority.CRITICAL,
        )
        assert msg.priority == MessagePriority.CRITICAL
        assert msg.priority.value == 3


# ===========================================================================
# Test MessageBus
# ===========================================================================

class TestMessageBus:
    def setup_method(self):
        self.bus = MessageBus()

    @pytest.mark.asyncio
    async def test_direct_send(self):
        agent = EchoAgent(agent_id="bus_echo")
        self.bus.register_handler("bus_echo", agent.handle_message)

        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="tester",
            recipient="bus_echo",
            content={"test": True},
        )
        response = await self.bus.send(msg)
        assert response is not None
        assert response.content["echo"] == {"test": True}

    @pytest.mark.asyncio
    async def test_send_to_missing_handler(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="tester",
            recipient="nonexistent",
        )
        response = await self.bus.send(msg)
        assert response.type == MessageType.ERROR

    @pytest.mark.asyncio
    async def test_topic_publish(self):
        received = []

        async def handler(msg):
            received.append(msg)
            return msg.reply({"ack": True})

        self.bus.subscribe("alerts", handler)
        msg = AgentMessage(
            type=MessageType.EVENT,
            sender="sensor",
            content={"level": "high"},
        )
        responses = await self.bus.publish("alerts", msg)
        assert len(received) == 1
        assert len(responses) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        received = []

        async def handler(msg):
            received.append(msg)
            return None

        self.bus.subscribe("topic1", handler)
        self.bus.unsubscribe("topic1", handler)

        msg = AgentMessage(type=MessageType.EVENT, sender="x")
        await self.bus.publish("topic1", msg)
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_message_history(self):
        agent = EchoAgent(agent_id="hist_echo")
        self.bus.register_handler("hist_echo", agent.handle_message)

        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="tester",
            recipient="hist_echo",
        )
        await self.bus.send(msg)

        history = self.bus.get_history()
        assert len(history) >= 2  # request + response

        history_filtered = self.bus.get_history(agent_id="tester")
        assert len(history_filtered) >= 1

    def test_unregister_handler(self):
        agent = EchoAgent(agent_id="unreg")
        self.bus.register_handler("unreg", agent.handle_message)
        self.bus.unregister_handler("unreg")
        assert "unreg" not in self.bus._handlers

    @pytest.mark.asyncio
    async def test_request_convenience(self):
        agent = EchoAgent(agent_id="req_echo")
        self.bus.register_handler("req_echo", agent.handle_message)

        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="tester",
            recipient="req_echo",
            content={"data": 42},
        )
        response = await self.bus.request(msg, timeout=5.0)
        assert response.content["echo"]["data"] == 42

    def test_clear_history(self):
        self.bus._history.append(
            AgentMessage(type=MessageType.EVENT, sender="x")
        )
        assert len(self.bus._history) > 0
        self.bus.clear_history()
        assert len(self.bus._history) == 0


# ===========================================================================
# Test AgentRegistry
# ===========================================================================

class TestAgentRegistry:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_register_agent(self):
        agent = EchoAgent(agent_id="reg_echo")
        self.registry.register(agent)
        assert self.registry.get_agent("reg_echo") is agent

    def test_deregister_agent(self):
        agent = EchoAgent(agent_id="dereg")
        self.registry.register(agent)
        self.registry.deregister("dereg")
        assert self.registry.get_agent("dereg") is None

    def test_find_by_capability(self):
        echo = EchoAgent(agent_id="cap_echo")
        adder = AdderAgent(agent_id="cap_adder")
        self.registry.register(echo)
        self.registry.register(adder)

        found = self.registry.find_by_capability("echo")
        assert len(found) == 1
        assert found[0].agent_id == "cap_echo"

        found_math = self.registry.find_by_capability("math")
        assert len(found_math) == 1
        assert found_math[0].agent_id == "cap_adder"

    def test_find_by_type(self):
        echo = EchoAgent(agent_id="type_echo")
        adder = AdderAgent(agent_id="type_adder")
        self.registry.register(echo)
        self.registry.register(adder)

        found = self.registry.find_by_type(EchoAgent)
        assert len(found) == 1

    def test_find_by_status(self):
        agent = EchoAgent(agent_id="status_test")
        self.registry.register(agent)
        found = self.registry.find_by_status(AgentStatus.IDLE)
        assert len(found) == 1

    def test_connect_bus(self):
        bus = MessageBus()
        agent = EchoAgent(agent_id="bus_test")
        self.registry.register(agent)
        self.registry.connect_bus(bus)
        assert agent._message_bus is bus
        assert "bus_test" in bus._handlers

    def test_summary(self):
        self.registry.register(EchoAgent(agent_id="s1"))
        self.registry.register(AdderAgent(agent_id="s2"))
        summary = self.registry.summary()
        assert summary["total_agents"] == 2
        assert len(summary["agents"]) == 2

    @pytest.mark.asyncio
    async def test_initialize_all(self):
        a1 = EchoAgent(agent_id="init1")
        a2 = EchoAgent(agent_id="init2")
        self.registry.register(a1)
        self.registry.register(a2)
        await self.registry.initialize_all()
        assert a1.status == AgentStatus.IDLE
        assert a2.status == AgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_shutdown_all(self):
        a1 = EchoAgent(agent_id="shut1")
        self.registry.register(a1)
        await self.registry.shutdown_all()
        assert a1.status == AgentStatus.STOPPED

    def test_get_all_agents(self):
        self.registry.register(EchoAgent(agent_id="all1"))
        self.registry.register(EchoAgent(agent_id="all2"))
        all_agents = self.registry.get_all_agents()
        assert len(all_agents) == 2


# ===========================================================================
# Test AgentContext
# ===========================================================================

class TestAgentContext:
    def setup_method(self):
        self.ctx = AgentContext(context_id="test_ctx")

    def test_get_set(self):
        self.ctx.set("key", "value", agent_id="tester")
        assert self.ctx.get("key") == "value"

    def test_get_default(self):
        assert self.ctx.get("nonexistent", 42) == 42

    def test_update(self):
        self.ctx.update({"a": 1, "b": 2}, agent_id="tester")
        assert self.ctx.get("a") == 1
        assert self.ctx.get("b") == 2

    def test_delete(self):
        self.ctx.set("del_key", "val")
        self.ctx.delete("del_key")
        assert not self.ctx.has("del_key")

    def test_has(self):
        self.ctx.set("exists", True)
        assert self.ctx.has("exists")
        assert not self.ctx.has("nope")

    def test_keys(self):
        self.ctx.set("k1", 1)
        self.ctx.set("k2", 2)
        keys = self.ctx.keys()
        assert "k1" in keys
        assert "k2" in keys

    def test_sections(self):
        self.ctx.set_section("agent_a", {"x": 10, "y": 20}, agent_id="agent_a")
        section = self.ctx.get_section("agent_a")
        assert section["x"] == 10

        self.ctx.update_section("agent_a", {"z": 30}, agent_id="agent_a")
        section = self.ctx.get_section("agent_a")
        assert section["z"] == 30
        assert section["x"] == 10

    def test_deep_copy_isolation(self):
        data = {"nested": [1, 2, 3]}
        self.ctx.set("mutable", data)
        retrieved = self.ctx.get("mutable")
        retrieved["nested"].append(4)
        # Original should be unchanged
        assert len(self.ctx.get("mutable")["nested"]) == 3

    def test_trace(self):
        self.ctx.add_trace("agent_1", "did_something", {"detail": "ok"})
        self.ctx.add_trace("agent_2", "did_other")
        trace = self.ctx.get_trace()
        assert len(trace) == 2
        assert trace[0]["agent_id"] == "agent_1"

    def test_trace_filter(self):
        self.ctx.add_trace("a1", "action1")
        self.ctx.add_trace("a2", "action2")
        filtered = self.ctx.get_trace(agent_id="a1")
        assert len(filtered) == 1

    def test_snapshot(self):
        self.ctx.set("snap_key", 42)
        snapshot = self.ctx.snapshot()
        assert snapshot["context_id"] == "test_ctx"
        assert "snap_key" in snapshot["state_keys"]

    def test_clear(self):
        self.ctx.set("a", 1)
        self.ctx.add_trace("x", "y")
        self.ctx.clear()
        assert self.ctx.keys() == []
        assert self.ctx.get_trace() == []

    def test_repr(self):
        r = repr(self.ctx)
        assert "test_ctx" in r


# ===========================================================================
# Test ExecutionPlan
# ===========================================================================

class TestExecutionPlan:
    def test_plan_creation(self):
        plan = ExecutionPlan(objective="test plan")
        task = ExecutionTask(id="t1", agent_id="a1", action="do_thing")
        plan.add_task(task)
        assert len(plan.tasks) == 1

    def test_validate_no_cycles(self):
        plan = ExecutionPlan()
        plan.add_task(ExecutionTask(id="a", agent_id="x", action="x"))
        plan.add_task(ExecutionTask(id="b", agent_id="x", action="x", dependencies=["a"]))
        plan.validate()  # Should not raise

    def test_validate_cycle_detected(self):
        plan = ExecutionPlan()
        plan.add_task(ExecutionTask(id="a", agent_id="x", action="x", dependencies=["b"]))
        plan.add_task(ExecutionTask(id="b", agent_id="x", action="x", dependencies=["a"]))
        with pytest.raises(ValueError, match="Cycle"):
            plan.validate()

    def test_validate_unknown_dependency_detected(self):
        plan = ExecutionPlan()
        plan.add_task(ExecutionTask(id="a", agent_id="x", action="x", dependencies=["missing"]))
        with pytest.raises(ValueError, match="unknown dependencies"):
            plan.validate()

    def test_get_ready_tasks(self):
        plan = ExecutionPlan()
        plan.add_task(ExecutionTask(id="a", agent_id="x", action="x"))
        plan.add_task(ExecutionTask(id="b", agent_id="x", action="x", dependencies=["a"]))
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "a"

    def test_all_completed(self):
        plan = ExecutionPlan()
        plan.add_task(ExecutionTask(id="a", agent_id="x", action="x", status=TaskStatus.COMPLETED))
        assert plan.all_completed

    def test_to_dict(self):
        plan = ExecutionPlan(objective="obj")
        plan.add_task(ExecutionTask(id="a", agent_id="x", action="y"))
        d = plan.to_dict()
        assert d["objective"] == "obj"
        assert len(d["tasks"]) == 1


# ===========================================================================
# Test MultiAgentExecutor
# ===========================================================================

class TestMultiAgentExecutor:
    def setup_method(self):
        self.registry = AgentRegistry()
        self.context = AgentContext()
        self.executor = MultiAgentExecutor(self.registry, self.context)

    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        echo = EchoAgent(agent_id="seq_echo")
        self.registry.register(echo)

        plan = self.executor.build_sequential_plan(
            "test sequential",
            [
                {"agent_id": "seq_echo", "action": "step1"},
                {"agent_id": "seq_echo", "action": "step2"},
            ],
        )
        result = await self.executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        assert all(t.status == TaskStatus.COMPLETED for t in result.tasks)

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        e1 = EchoAgent(agent_id="par_1")
        e2 = EchoAgent(agent_id="par_2")
        self.registry.register(e1)
        self.registry.register(e2)

        plan = self.executor.build_parallel_plan(
            "test parallel",
            [
                {"agent_id": "par_1", "action": "task_a"},
                {"agent_id": "par_2", "action": "task_b"},
            ],
        )
        result = await self.executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        assert len(result.tasks) == 2

    @pytest.mark.asyncio
    async def test_fan_out_fan_in(self):
        e1 = EchoAgent(agent_id="fan_1")
        e2 = EchoAgent(agent_id="fan_2")
        agg = EchoAgent(agent_id="fan_agg")
        self.registry.register(e1)
        self.registry.register(e2)
        self.registry.register(agg)

        plan = self.executor.build_fan_out_fan_in_plan(
            "test fan-out/fan-in",
            [
                {"agent_id": "fan_1", "action": "compute_a"},
                {"agent_id": "fan_2", "action": "compute_b"},
            ],
            {"agent_id": "fan_agg", "action": "aggregate"},
        )
        result = await self.executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        assert len(result.tasks) == 3

    @pytest.mark.asyncio
    async def test_task_failure_handling(self):
        fail = FailAgent(agent_id="fail_agent")
        self.registry.register(fail)

        plan = ExecutionPlan(objective="test failure")
        plan.add_task(ExecutionTask(
            id="fail_task",
            agent_id="fail_agent",
            action="fail",
            max_retries=1,
        ))
        result = await self.executor.execute(plan)
        assert result.status == TaskStatus.FAILED
        assert result.tasks[0].status == TaskStatus.FAILED
        assert result.tasks[0].retries == 2  # 1 original + 1 retry

    @pytest.mark.asyncio
    async def test_dependency_results_passed(self):
        adder = AdderAgent(agent_id="dep_adder")
        self.registry.register(adder)

        plan = ExecutionPlan(objective="dependency test")
        plan.add_task(ExecutionTask(
            id="first", agent_id="dep_adder", action="add",
            params={"a": 1, "b": 2},
        ))
        plan.add_task(ExecutionTask(
            id="second", agent_id="dep_adder", action="add",
            params={"a": 3, "b": 4},
            dependencies=["first"],
        ))
        result = await self.executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        second_task = [t for t in result.tasks if t.id == "second"][0]
        assert "_dependency_results" in second_task.params

    @pytest.mark.asyncio
    async def test_missing_agent_failure(self):
        plan = ExecutionPlan(objective="missing agent")
        plan.add_task(ExecutionTask(id="t1", agent_id="nonexistent", action="x"))
        result = await self.executor.execute(plan)
        assert result.tasks[0].status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_context_updated_during_execution(self):
        echo = EchoAgent(agent_id="ctx_echo")
        self.registry.register(echo)

        plan = self.executor.build_sequential_plan(
            "context test",
            [{"agent_id": "ctx_echo", "action": "test"}],
        )
        await self.executor.execute(plan)
        assert self.context.has("current_plan_id")
        assert self.context.has("plan_result")

    def test_execution_history(self):
        assert self.executor.get_history() == []

    @pytest.mark.asyncio
    async def test_blocked_tasks_skipped(self):
        fail = FailAgent(agent_id="block_fail")
        echo = EchoAgent(agent_id="block_echo")
        self.registry.register(fail)
        self.registry.register(echo)

        plan = ExecutionPlan(objective="blocked test")
        plan.add_task(ExecutionTask(
            id="first", agent_id="block_fail", action="x", max_retries=0,
        ))
        plan.add_task(ExecutionTask(
            id="second", agent_id="block_echo", action="y",
            dependencies=["first"],
        ))
        result = await self.executor.execute(plan)
        assert result.tasks[0].status == TaskStatus.FAILED
        assert result.tasks[1].status == TaskStatus.SKIPPED


# ===========================================================================
# Test domain agents inherit from BaseAgent
# ===========================================================================

class TestAgentInheritance:
    """Verify all domain agents properly inherit from BaseAgent."""

    def test_planning_agent_is_base_agent(self):
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        assert isinstance(agent, BaseAgent)
        assert "task_decomposition" in agent.get_capabilities()

    def test_analysis_agent_is_base_agent(self):
        from agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent()
        assert isinstance(agent, BaseAgent)
        assert "scheme_comparison" in agent.get_capabilities()

    def test_report_agent_is_base_agent(self):
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        assert isinstance(agent, BaseAgent)
        assert "report_generation" in agent.get_capabilities()

    def test_safety_agent_is_base_agent(self):
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        assert isinstance(agent, BaseAgent)
        assert "odd_check" in agent.get_capabilities()

    def test_handuo_agent_is_base_agent(self):
        from agents.handuo_agent import HanduoAgent
        agent = HanduoAgent()
        assert isinstance(agent, BaseAgent)
        assert "domain_qa" in agent.get_capabilities()

    def test_rl_dispatch_agent_is_base_agent(self):
        from agents.rl_dispatch_agent import RLDispatchAgent
        agent = RLDispatchAgent()
        assert isinstance(agent, BaseAgent)
        assert "rl_dispatch" in agent.get_capabilities()

    def test_dev_planner_is_base_agent(self):
        from agents.dev_planner import DevPlannerAgent
        agent = DevPlannerAgent()
        assert isinstance(agent, BaseAgent)
        assert "requirement_analysis" in agent.get_capabilities()

    def test_dev_reviewer_is_base_agent(self):
        from agents.dev_reviewer import DevReviewerAgent
        agent = DevReviewerAgent()
        assert isinstance(agent, BaseAgent)
        assert "code_review" in agent.get_capabilities()

    def test_dev_tester_is_base_agent(self):
        from agents.dev_tester import DevTesterAgent
        agent = DevTesterAgent()
        assert isinstance(agent, BaseAgent)
        assert "test_generation" in agent.get_capabilities()

    def test_dev_orchestrator_is_base_agent(self):
        from agents.dev_orchestrator import DevOrchestratorAgent
        agent = DevOrchestratorAgent()
        assert isinstance(agent, BaseAgent)
        assert "dev_pipeline" in agent.get_capabilities()

    def test_orchestrator_is_base_agent(self):
        from agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        assert isinstance(agent, BaseAgent)
        assert "intent_classification" in agent.get_capabilities()


# ===========================================================================
# Test OrchestratorAgent multi-agent features
# ===========================================================================

class TestOrchestratorMultiAgent:
    def test_orchestrator_with_registry(self):
        from agents.orchestrator import OrchestratorAgent
        registry = AgentRegistry()
        orch = OrchestratorAgent(registry=registry)
        assert orch.registry is registry

    def test_platform_summary(self):
        from agents.orchestrator import OrchestratorAgent
        orch = OrchestratorAgent()
        summary = orch.get_platform_summary()
        assert "skills_count" in summary
        assert "tools_count" in summary
        assert summary["has_registry"] is False

    def test_get_registered_agents_empty(self):
        from agents.orchestrator import OrchestratorAgent
        orch = OrchestratorAgent()
        assert orch.get_registered_agents() == []

    def test_get_registered_agents_with_registry(self):
        from agents.orchestrator import OrchestratorAgent
        registry = AgentRegistry()
        echo = EchoAgent(agent_id="orch_echo")
        registry.register(echo)
        orch = OrchestratorAgent(registry=registry)
        agents = orch.get_registered_agents()
        assert len(agents) == 1
        assert agents[0]["id"] == "orch_echo"

    @pytest.mark.asyncio
    async def test_collaborative_workflow(self):
        from agents.orchestrator import OrchestratorAgent
        registry = AgentRegistry()
        e1 = EchoAgent(agent_id="cw_echo1")
        e2 = EchoAgent(agent_id="cw_echo2")
        registry.register(e1)
        registry.register(e2)
        orch = OrchestratorAgent(registry=registry)

        result = await orch.run_collaborative_workflow(
            objective="test collaboration",
            agent_tasks=[
                {"agent_id": "cw_echo1", "action": "step1"},
                {"agent_id": "cw_echo2", "action": "step2", "dependencies": []},
            ],
        )
        assert result["status"] == "completed"
        assert len(result["tasks"]) == 2


# ===========================================================================
# Integration: Full multi-agent scenario
# ===========================================================================

class TestMultiAgentIntegration:
    @pytest.mark.asyncio
    async def test_full_multi_agent_scenario(self):
        """End-to-end test: registry + bus + executor + agents."""
        # Create infrastructure
        registry = AgentRegistry()
        bus = MessageBus()
        context = AgentContext(context_id="e2e_test")

        # Register agents
        echo = EchoAgent(agent_id="e2e_echo")
        adder = AdderAgent(agent_id="e2e_adder")
        registry.register(echo)
        registry.register(adder)
        registry.connect_bus(bus)

        # Initialize
        await registry.initialize_all()

        # Direct message via bus
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="e2e_echo",
            content={"hello": "world"},
        )
        response = await bus.send(msg)
        assert response.content["echo"]["hello"] == "world"

        # Execute plan
        executor = MultiAgentExecutor(registry, context)
        plan = executor.build_sequential_plan(
            "e2e test",
            [
                {"agent_id": "e2e_echo", "action": "step1", "params": {"data": "a"}},
                {"agent_id": "e2e_adder", "action": "add", "params": {"a": 5, "b": 3}},
            ],
        )
        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED

        # Verify context captured trace
        trace = context.get_trace()
        assert len(trace) > 0

        # Verify history
        history = bus.get_history()
        assert len(history) > 0

        # Shutdown
        await registry.shutdown_all()
        assert echo.status == AgentStatus.STOPPED
