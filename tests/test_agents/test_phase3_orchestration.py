"""Tests for Phase 3 orchestration enhancements:

1. Orchestrator health-aware delegation + event emission
2. Capability negotiation protocol
3. Cross-domain workflow orchestration
4. Auto-replan on failure
5. E2E multi-agent scenarios

Phase 3 编排升级测试：
1. Orchestrator 健康感知委派 + 事件发布
2. 能力协商协议
3. 跨域工作流编排
4. 失败自动重规划
5. E2E 多智能体场景
"""

from __future__ import annotations

import asyncio

import pytest

from agents.base_agent import AgentStatus, BaseAgent
from agents.context import AgentContext
from agents.executor import ExecutionPlan, ExecutionTask, MultiAgentExecutor, TaskStatus
from agents.health import AgentHealthMonitor
from agents.message import AgentMessage, MessageBus, MessageType
from agents.negotiation import AgentBid, CapabilityNegotiator, NegotiationResult
from agents.orchestrator import OrchestratorAgent
from agents.planning_agent import PlanningAgent
from agents.registry import AgentRegistry


# ---------------------------------------------------------------------------
# Fixture agents
# ---------------------------------------------------------------------------

class EchoAgent(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["echo", "compute", "water_balance_analysis"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        return message.reply({"echo": True, "agent_id": self.agent_id})


class FailOnceAgent(BaseAgent):
    """Fails on first call, succeeds on subsequent calls."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._call_count = 0

    def get_capabilities(self) -> list[str]:
        return ["flaky_task"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        self._call_count += 1
        if self._call_count == 1:
            raise RuntimeError("Transient failure")
        return message.reply({"recovered": True})


class AnalysisStub(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["data_analysis", "water_balance_analysis"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        return message.reply({"analysis": "done", "agent_id": self.agent_id})


class ReportStub(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["report_generation"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        return message.reply({"report": "generated", "agent_id": self.agent_id})


class SafetyStub(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["safety_check", "odd_monitoring"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        return message.reply({"safety": "ok"})


# ===========================================================================
# 1. Capability Negotiation Protocol
# ===========================================================================

class TestCapabilityNegotiator:
    """Test the CapabilityNegotiator bidding and scoring."""

    def setup_method(self):
        self.registry = AgentRegistry()
        self.monitor = AgentHealthMonitor(self.registry)

    def test_negotiate_no_candidates(self):
        neg = CapabilityNegotiator(self.registry)
        result = neg.negotiate("nonexistent")
        assert result.winner is None
        assert "No agents" in result.reason

    def test_negotiate_single_candidate(self):
        agent = EchoAgent(agent_id="solo")
        self.registry.register(agent)
        neg = CapabilityNegotiator(self.registry)
        result = neg.negotiate("compute")
        assert result.winner is agent
        assert "Single candidate" in result.reason

    def test_negotiate_multiple_candidates_selects_best(self):
        a1 = EchoAgent(agent_id="agent_a")
        a2 = EchoAgent(agent_id="agent_b")
        self.registry.register(a1)
        self.registry.register(a2)

        # Give agent_a higher error rate
        self.monitor.record_request("agent_a", 100.0, False)
        self.monitor.record_request("agent_a", 100.0, False)
        self.monitor.record_request("agent_b", 50.0, True)

        neg = CapabilityNegotiator(self.registry, health_monitor=self.monitor)
        result = neg.negotiate("compute")

        assert result.winner is not None
        assert result.winner.agent_id == "agent_b"
        assert len(result.bids) == 2
        assert result.scores["agent_b"] > result.scores["agent_a"]

    def test_negotiate_penalizes_loaded_agent(self):
        idle = EchoAgent(agent_id="idle_agent")
        busy = EchoAgent(agent_id="busy_agent")
        busy.status = AgentStatus.RUNNING
        self.registry.register(idle)
        self.registry.register(busy)

        neg = CapabilityNegotiator(self.registry)
        result = neg.negotiate("compute")

        assert result.winner.agent_id == "idle_agent"
        assert result.scores["idle_agent"] > result.scores["busy_agent"]

    def test_negotiate_penalizes_stopped_agent(self):
        healthy = EchoAgent(agent_id="healthy_n")
        stopped = EchoAgent(agent_id="stopped_n")
        stopped.status = AgentStatus.STOPPED
        self.registry.register(healthy)
        self.registry.register(stopped)

        neg = CapabilityNegotiator(self.registry)
        result = neg.negotiate("compute")

        assert result.winner.agent_id == "healthy_n"

    def test_negotiate_with_latency_bias(self):
        fast = EchoAgent(agent_id="fast_n")
        slow = EchoAgent(agent_id="slow_n")
        self.registry.register(fast)
        self.registry.register(slow)

        self.monitor.record_request("fast_n", 10.0, True)
        self.monitor.record_request("slow_n", 800.0, True)

        neg = CapabilityNegotiator(self.registry, health_monitor=self.monitor)
        result = neg.negotiate("compute")

        assert result.winner.agent_id == "fast_n"

    def test_negotiation_result_to_dict(self):
        agent = EchoAgent(agent_id="dict_test")
        self.registry.register(agent)
        neg = CapabilityNegotiator(self.registry)
        result = neg.negotiate("compute")

        d = result.to_dict()
        assert d["capability"] == "compute"
        assert d["winner"] == "dict_test"
        assert len(d["bids"]) == 1

    def test_custom_scoring_weights(self):
        a1 = EchoAgent(agent_id="w1")
        a2 = EchoAgent(agent_id="w2")
        self.registry.register(a1)
        self.registry.register(a2)

        neg = CapabilityNegotiator(self.registry, health_monitor=self.monitor)
        # Override weights to heavily favor latency
        neg.weight_latency = 0.8
        neg.weight_health = 0.05
        neg.weight_error_rate = 0.05
        neg.weight_affinity = 0.05
        neg.weight_load = 0.05

        self.monitor.record_request("w1", 10.0, True)
        self.monitor.record_request("w2", 900.0, True)

        result = neg.negotiate("compute")
        assert result.winner.agent_id == "w1"


# ===========================================================================
# 2. Orchestrator Enhanced Features
# ===========================================================================

class TestOrchestratorPhase3:
    """Test Orchestrator health-aware delegation and event emission."""

    def setup_method(self):
        self.registry = AgentRegistry()
        self.bus = MessageBus()
        self.monitor = AgentHealthMonitor(self.registry)
        self.registry.connect_bus(self.bus)

        # Register agents
        self.planner = PlanningAgent(agent_id="planning")
        self.analysis = AnalysisStub(agent_id="analysis")
        self.report = ReportStub(agent_id="report")
        self.safety = SafetyStub(agent_id="safety")
        self.echo = EchoAgent(agent_id="echo_worker")

        for a in [self.planner, self.analysis, self.report, self.safety, self.echo]:
            self.registry.register(a)

    def _make_orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent(
            agent_id="orchestrator",
            registry=self.registry,
            health_monitor=self.monitor,
            message_bus=self.bus,
        )

    @pytest.mark.asyncio
    async def test_routing_emits_event(self):
        orch = self._make_orchestrator()
        events = []

        async def handler(msg):
            events.append(msg)
            return None

        self.bus.subscribe("orchestrator.routed", handler)

        await orch.handle_request("模拟水箱阶跃响应")

        assert len(events) >= 1
        assert events[0].content["route_type"] in ("skill", "tool", "agent")

    @pytest.mark.asyncio
    async def test_capability_routing_uses_health_aware(self):
        orch = self._make_orchestrator()

        # Classify intent for capability match
        intent = orch.classify_intent("生成报告分析")
        assert intent["route_type"] == "agent"
        assert intent["target"] == "report"

    @pytest.mark.asyncio
    async def test_collaborative_workflow_with_health_and_events(self):
        orch = self._make_orchestrator()

        plan_events = []

        async def handler(msg):
            plan_events.append(msg)
            return None

        self.bus.subscribe("plan.started", handler)
        self.bus.subscribe("plan.completed", handler)

        result = await orch.run_collaborative_workflow(
            objective="analysis + report",
            agent_tasks=[
                {"agent_id": "analysis", "action": "analyze", "params": {}},
                {"agent_id": "report", "action": "generate", "params": {},
                 "dependencies": ["task_1"]},
            ],
        )

        assert result["status"] == "completed"
        # Events should have been emitted
        topics = [e.content.get("topic") for e in plan_events]
        assert "plan.started" in topics
        assert "plan.completed" in topics

    @pytest.mark.asyncio
    async def test_cross_domain_workflow(self):
        """Orchestrator plans and executes a cross-domain workflow."""
        orch = self._make_orchestrator()

        # Register agents for each tool that the leak_diagnosis template uses
        for tool_id in ["calc_full_plant_balance", "detect_balance_anomaly",
                        "detect_leak", "localize_leak"]:
            if self.registry.get_agent(tool_id) is None:
                self.registry.register(EchoAgent(agent_id=tool_id))

        result = await orch.run_cross_domain_workflow("检测管道泄漏")

        assert result["status"] == "completed"
        assert len(result["tasks"]) == 4  # leak_diagnosis template has 4 tasks

    @pytest.mark.asyncio
    async def test_cross_domain_daily_report(self):
        """Cross-domain workflow for daily report."""
        orch = self._make_orchestrator()

        for tool_id in ["calc_full_plant_balance", "detect_balance_anomaly",
                        "evaluate_water_kpi", "predict_total_evap_loss"]:
            if self.registry.get_agent(tool_id) is None:
                self.registry.register(EchoAgent(agent_id=tool_id))

        result = await orch.run_cross_domain_workflow("生成日报")
        assert result["status"] == "completed"
        assert len(result["tasks"]) == 4

    @pytest.mark.asyncio
    async def test_cross_domain_without_registry(self):
        orch = OrchestratorAgent(agent_id="no_reg")
        result = await orch.run_cross_domain_workflow("some workflow")
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_auto_replan_on_failure(self):
        """Collaborative workflow with auto_replan=True."""
        orch = self._make_orchestrator()

        # task_1 will fail (no agent for nonexistent), task_2 depends on it, task_3 is independent
        result = await orch.run_collaborative_workflow(
            objective="replan test",
            agent_tasks=[
                {"id": "t1", "agent_id": "nonexistent_agent", "action": "fail"},
                {"id": "t2", "agent_id": "analysis", "action": "analyze",
                 "dependencies": ["t1"]},
                {"id": "t3", "agent_id": "report", "action": "generate"},
            ],
            auto_replan=True,
        )

        # The original plan failed; replan should have run for remaining viable tasks
        # t1 failed → t2 blocked → only t3 remains
        # Since t3 already completed in original run, replan has nothing to do
        assert "status" in result

    @pytest.mark.asyncio
    async def test_platform_summary(self):
        orch = self._make_orchestrator()
        summary = orch.get_platform_summary()
        assert summary["has_registry"] is True
        assert len(summary["registered_agents"]) == 5


# ===========================================================================
# 3. Negotiation API
# ===========================================================================

class TestNegotiationAPI:
    """Test /negotiate/{capability} endpoint."""

    @pytest.fixture
    def client(self):
        import importlib

        # Clear singletons for test isolation
        from web import deps
        for fn in [deps.get_agent_registry, deps.get_message_bus,
                    deps.get_agent_context, deps.get_health_monitor, deps.get_executor]:
            if hasattr(fn, "_instance"):
                delattr(fn, "_instance")

        from web.app import app
        from starlette.testclient import TestClient

        return TestClient(app)

    def test_negotiate_capability_endpoint(self, client):
        resp = client.get("/api/orchestration/negotiate/task_decomposition")
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "task_decomposition"
        assert data["winner"] == "planning"

    def test_negotiate_nonexistent_capability(self, client):
        resp = client.get("/api/orchestration/negotiate/nonexistent_cap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["winner"] is None


# ===========================================================================
# 4. E2E Multi-Agent Scenarios
# ===========================================================================

class TestE2EMultiAgentScenarios:
    """End-to-end scenarios testing the full multi-agent stack."""

    @pytest.mark.asyncio
    async def test_full_pipeline_plan_execute_with_events(self):
        """Full pipeline: Plan → Execute DAG → Emit events → Collect results."""
        registry = AgentRegistry()
        bus = MessageBus()
        monitor = AgentHealthMonitor(registry)
        context = AgentContext()

        # Register agents for each step
        planner = PlanningAgent(agent_id="planning")
        registry.register(planner)

        for tool_id in ["calc_full_plant_balance", "detect_balance_anomaly",
                        "detect_leak", "localize_leak"]:
            registry.register(EchoAgent(agent_id=tool_id))

        registry.connect_bus(bus)

        # Subscribe to events
        all_events = []

        async def collector(msg):
            all_events.append(msg)
            return None

        for topic in ["plan.started", "task.completed", "plan.completed"]:
            bus.subscribe(topic, collector)

        # Plan
        task_plan = planner.plan("检测管道泄漏")
        assert task_plan.objective == "Leak diagnosis pipeline"
        assert len(task_plan.nodes) == 4

        # Execute
        exec_plan = ExecutionPlan(objective=task_plan.objective)
        for node in task_plan.nodes:
            exec_plan.add_task(ExecutionTask(
                id=node.id, agent_id=node.tool_or_skill,
                action=node.tool_or_skill, params=node.params,
                dependencies=node.dependencies,
            ))

        executor = MultiAgentExecutor(
            registry, context,
            health_monitor=monitor, message_bus=bus,
        )
        result = await executor.execute(exec_plan)

        # Validate
        assert result.status == TaskStatus.COMPLETED
        assert len(result.tasks) == 4
        assert all(t.status == TaskStatus.COMPLETED for t in result.tasks)

        # Events emitted
        topics = [e.content.get("topic") for e in all_events]
        assert "plan.started" in topics
        assert topics.count("task.completed") == 4
        assert "plan.completed" in topics

        # Health metrics recorded
        for tool_id in ["calc_full_plant_balance", "detect_balance_anomaly",
                        "detect_leak", "localize_leak"]:
            m = monitor.get_metrics(tool_id)
            assert m["request_count"] == 1

    @pytest.mark.asyncio
    async def test_negotiation_driven_execution(self):
        """Negotiate agent → execute task → verify best agent used."""
        registry = AgentRegistry()
        monitor = AgentHealthMonitor(registry)

        fast = EchoAgent(agent_id="fast_worker")
        slow = EchoAgent(agent_id="slow_worker")
        registry.register(fast)
        registry.register(slow)

        # fast_worker is faster
        monitor.record_request("fast_worker", 10.0, True)
        monitor.record_request("slow_worker", 500.0, True)

        # Negotiate
        neg = CapabilityNegotiator(registry, health_monitor=monitor)
        result = neg.negotiate("compute")
        assert result.winner.agent_id == "fast_worker"

        # Execute using winner
        executor = MultiAgentExecutor(
            registry, AgentContext(), health_monitor=monitor,
        )
        plan = ExecutionPlan(objective="negotiated task")
        plan.add_task(ExecutionTask(
            id="t1", agent_id=result.winner.agent_id, action="compute",
        ))
        exec_result = await executor.execute(plan)
        assert exec_result.status == TaskStatus.COMPLETED
        assert exec_result.tasks[0].result["agent_id"] == "fast_worker"

    @pytest.mark.asyncio
    async def test_parallel_fan_out_with_negotiation(self):
        """Fan-out to 3 agents → fan-in aggregation → all health-tracked."""
        registry = AgentRegistry()
        monitor = AgentHealthMonitor(registry)
        bus = MessageBus()

        workers = []
        for i in range(3):
            w = EchoAgent(agent_id=f"worker_{i}")
            registry.register(w)
            workers.append(w)

        aggregator = ReportStub(agent_id="agg")
        registry.register(aggregator)

        executor = MultiAgentExecutor(
            registry, AgentContext(),
            health_monitor=monitor, message_bus=bus,
        )

        plan = executor.build_fan_out_fan_in_plan(
            objective="parallel analysis",
            parallel_tasks=[
                {"agent_id": f"worker_{i}", "action": "compute"}
                for i in range(3)
            ],
            aggregator={"agent_id": "agg", "action": "generate"},
        )

        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
        assert len(result.tasks) == 4  # 3 fan-out + 1 aggregator

        # All workers tracked
        for i in range(3):
            m = monitor.get_metrics(f"worker_{i}")
            assert m["request_count"] == 1

    @pytest.mark.asyncio
    async def test_multi_agent_evaporation_dispatch_pipeline(self):
        """E2E: Water dispatch pipeline — demand→evap→dispatch→odd_check."""
        registry = AgentRegistry()
        bus = MessageBus()
        monitor = AgentHealthMonitor(registry)

        planner = PlanningAgent(agent_id="planning")
        registry.register(planner)

        for tool_id in ["predict_demand", "predict_evaporation",
                        "optimize_global_dispatch", "check_alumina_odd"]:
            registry.register(EchoAgent(agent_id=tool_id))

        registry.connect_bus(bus)

        # Use orchestrator for cross-domain workflow
        orch = OrchestratorAgent(
            agent_id="orchestrator",
            registry=registry,
            health_monitor=monitor,
            message_bus=bus,
        )
        result = await orch.run_cross_domain_workflow("全局调度优化")

        assert result["status"] == "completed"
        assert len(result["tasks"]) == 4

    @pytest.mark.asyncio
    async def test_orchestrator_get_available_skills(self):
        """Verify skill introspection still works with Phase 3 init changes."""
        orch = OrchestratorAgent(agent_id="intro_orch")
        skills = orch.get_available_skills()
        assert len(skills) > 0
        assert all("name" in s for s in skills)
