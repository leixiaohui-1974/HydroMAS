"""Tests for Phase 6 — Intelligence Upgrade.
Phase 6 测试 — 智能升级。

Covers:
- IntentClassifier (domain classification, multi-level routing, compound intent, history)
- AdaptiveScheduler (performance profiles, recommendations, best agent selection)
- Enhanced CapabilityNegotiator (history-based preferences)
"""

import pytest

from agents.adaptive_scheduler import AdaptiveScheduler
from agents.base_agent import BaseAgent
from agents.intent_classifier import IntentClassifier, IntentResult
from agents.message import AgentMessage, MessageType
from agents.negotiation import CapabilityNegotiator
from agents.registry import AgentRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockAgent(BaseAgent):
    def __init__(self, agent_id: str, capabilities: list[str] | None = None):
        super().__init__(agent_id=agent_id)
        self._caps = capabilities or ["test"]

    def get_capabilities(self) -> list[str]:
        return self._caps

    async def handle_message(self, msg: AgentMessage) -> AgentMessage:
        return msg.reply({"echo": msg.content})


# ===========================================================================
# IntentClassifier tests
# ===========================================================================

class TestIntentClassifier:
    @pytest.fixture
    def classifier(self):
        return IntentClassifier(
            skill_triggers={
                "forecast_skill": ["预报", "forecast", "predict water level"],
                "warning_skill": ["预警", "warning", "水位超标"],
                "leak_diagnosis": ["泄漏检测", "leak detection", "漏水"],
            },
            tool_keywords={
                "simulate_tank": ["仿真", "simulate", "simulation"],
                "check_odd": ["ODD", "安全", "safety"],
                "optimize_schedule": ["调度", "schedule"],
            },
            capability_keywords={
                "code_review": ["代码审查", "code review"],
                "report_generation": ["生成报告", "generate report"],
            },
        )

    def test_classify_skill(self, classifier):
        result = classifier.classify("forecast predict water level future")
        assert result.route_type == "skill"
        assert result.target == "forecast_skill"
        assert result.confidence > 0

    def test_classify_tool(self, classifier):
        result = classifier.classify("请进行仿真模拟")
        assert result.route_type in ("skill", "tool")
        assert result.confidence > 0

    def test_classify_capability(self, classifier):
        result = classifier.classify("请帮我做代码审查")
        assert result.route_type == "capability"
        assert result.target == "code_review"

    def test_classify_fallback_to_planning(self, classifier):
        result = classifier.classify("你好")
        assert result.route_type == "planning"
        assert result.target == "planning"

    def test_classify_domain_safety(self, classifier):
        domain, conf = classifier.classify_domain("检查ODD安全边界")
        assert domain == "safety"
        assert conf > 0

    def test_classify_domain_prediction(self, classifier):
        domain, conf = classifier.classify_domain("预测未来水位变化趋势")
        assert domain == "prediction"

    def test_classify_domain_diagnostics(self, classifier):
        domain, conf = classifier.classify_domain("进行泄漏检测和异常分析")
        assert domain == "diagnostics"

    def test_classify_domain_general(self, classifier):
        domain, conf = classifier.classify_domain("hello world")
        assert domain == "general"

    def test_compound_detection(self, classifier):
        results = classifier.classify_compound("先预报水位再检查ODD安全")
        assert len(results) >= 2
        targets = [r.target for r in results]
        assert "forecast_skill" in targets or "check_odd" in targets

    def test_compound_empty(self, classifier):
        results = classifier.classify_compound("你好世界")
        assert len(results) == 0

    def test_intent_history(self, classifier):
        classifier.classify("请进行水位预报")
        classifier.classify("进行仿真模拟")
        history = classifier.get_intent_history(limit=5)
        assert len(history) >= 2

    def test_routing_stats(self, classifier):
        classifier.classify("请进行水位预报")
        stats = classifier.get_routing_stats()
        assert stats["total_classifications"] >= 1
        assert "by_route_type" in stats
        assert "by_domain" in stats


class TestIntentResult:
    def test_to_dict(self):
        result = IntentResult(
            route_type="skill",
            target="forecast_skill",
            confidence=0.85,
            domain="prediction",
            matched_keywords=["预报"],
        )
        d = result.to_dict()
        assert d["route_type"] == "skill"
        assert d["confidence"] == 0.85
        assert d["domain"] == "prediction"


# ===========================================================================
# AdaptiveScheduler tests
# ===========================================================================

class TestAdaptiveScheduler:
    def test_record_and_profile(self):
        sched = AdaptiveScheduler()
        sched.record_execution("a1", "analyze", 150.0, success=True)
        sched.record_execution("a1", "analyze", 200.0, success=True)
        sched.record_execution("a1", "analyze", 0.0, success=False)
        profile = sched.get_profile("a1")
        assert profile["total_tasks"] == 3
        assert profile["successful_tasks"] == 2
        assert profile["failed_tasks"] == 1
        assert profile["avg_duration_ms"] == 175.0

    def test_recommend_with_history(self):
        sched = AdaptiveScheduler()
        for _ in range(10):
            sched.record_execution("a1", "analyze", 100.0, success=True)
        rec = sched.recommend("a1", "analyze")
        assert rec.confidence > 0.5
        assert rec.recommended_timeout_sec > 0

    def test_recommend_no_history(self):
        sched = AdaptiveScheduler()
        rec = sched.recommend("unknown", "action")
        assert rec.confidence == 0.1
        assert rec.recommended_timeout_sec == 30.0

    def test_recommend_high_failure_rate(self):
        sched = AdaptiveScheduler()
        for _ in range(5):
            sched.record_execution("a1", "flaky", 100.0, success=True)
        for _ in range(5):
            sched.record_execution("a1", "flaky", 0.0, success=False)
        rec = sched.recommend("a1", "flaky")
        assert rec.recommended_max_retries >= 2

    def test_find_best_agent_for_action(self):
        sched = AdaptiveScheduler()
        for _ in range(10):
            sched.record_execution("fast_agent", "analyze", 50.0, success=True)
        for _ in range(10):
            sched.record_execution("slow_agent", "analyze", 500.0, success=True)
        best = sched.find_best_agent_for_action("analyze")
        assert best == "fast_agent"

    def test_find_best_agent_unknown_action(self):
        sched = AdaptiveScheduler()
        best = sched.find_best_agent_for_action("unknown")
        assert best is None

    def test_scheduling_status(self):
        sched = AdaptiveScheduler()
        sched.record_execution("a1", "analyze", 100.0, success=True)
        sched.record_execution("a2", "report", 200.0, success=True)
        status = sched.get_scheduling_status()
        assert status["total_agents_profiled"] == 2
        assert status["total_actions_tracked"] == 2
        assert status["total_tasks_recorded"] == 2

    def test_timeout_tracking(self):
        sched = AdaptiveScheduler()
        sched.record_execution("a1", "slow", 0.0, success=False, timed_out=True)
        sched.record_execution("a1", "slow", 0.0, success=False, timed_out=True)
        profile = sched.get_profile("a1")
        assert profile["timeout_count"] == 2


# ===========================================================================
# Enhanced Negotiation tests
# ===========================================================================

class TestEnhancedNegotiation:
    def _build_registry(self):
        registry = AgentRegistry()
        a1 = MockAgent("a1", capabilities=["analysis"])
        a2 = MockAgent("a2", capabilities=["analysis"])
        registry.register(a1)
        registry.register(a2)
        return registry

    def test_negotiation_records_history(self):
        registry = self._build_registry()
        neg = CapabilityNegotiator(registry)
        neg.negotiate("analysis")
        neg.negotiate("analysis")
        history = neg.get_negotiation_history()
        assert len(history) == 2

    def test_preference_learning(self):
        registry = self._build_registry()
        neg = CapabilityNegotiator(registry)
        for _ in range(5):
            neg.negotiate("analysis")
        pref = neg.get_preference("analysis")
        assert pref["total"] == 5
        assert pref["top_agent"] is not None

    def test_get_all_preferences(self):
        registry = self._build_registry()
        neg = CapabilityNegotiator(registry)
        neg.negotiate("analysis")
        prefs = neg.get_all_preferences()
        assert "analysis" in prefs

    def test_no_history_for_unknown_capability(self):
        registry = self._build_registry()
        neg = CapabilityNegotiator(registry)
        pref = neg.get_preference("unknown")
        assert pref["total"] == 0
