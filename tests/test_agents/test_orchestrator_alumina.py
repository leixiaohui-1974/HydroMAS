"""Phase 3 tests for orchestrator alumina-specific routing and skill loading.
Phase 3 编排器氧化铝路由与技能加载测试。

Tests verify that TOOL_KEYWORDS and skill trigger phrases correctly
route alumina-refinery domain intents to the right target.
"""

from agents.orchestrator import OrchestratorAgent


class TestOrchestratorAluminaRouting:
    """Test alumina-specific intent classification and skill loading."""

    def setup_method(self):
        self.agent = OrchestratorAgent()

    # ------------------------------------------------------------------
    # Tool-level routing (Level 2)
    # ------------------------------------------------------------------

    def test_classify_intent_water_balance(self):
        """'全厂水平衡核算' should route to tool (calc_full_plant_balance)."""
        result = self.agent.classify_intent("全厂水平衡核算")
        assert result["route_type"] == "tool"
        assert result["target"] == "calc_full_plant_balance"

    def test_classify_intent_network_sim(self):
        """'管网仿真' should route to tool (simulate_network)."""
        result = self.agent.classify_intent("管网仿真")
        assert result["route_type"] == "tool"
        assert result["target"] == "simulate_network"

    def test_classify_intent_alumina_odd(self):
        """'氧化铝ODD' should route to tool (check_alumina_odd)."""
        result = self.agent.classify_intent("氧化铝ODD")
        assert result["route_type"] == "tool"
        assert result["target"] == "check_alumina_odd"

    # ------------------------------------------------------------------
    # Skill-level routing (Level 1 -- skills take priority)
    # ------------------------------------------------------------------

    def test_classify_intent_leak_detection(self):
        """'泄漏检测' should route to skill (leak_diagnosis)."""
        result = self.agent.classify_intent("泄漏检测")
        assert result["route_type"] == "skill"
        assert result["target"] == "leak_diagnosis"

    def test_classify_intent_evaporation(self):
        """'蒸发优化' should route to skill (evap_optimization)."""
        result = self.agent.classify_intent("蒸发优化")
        assert result["route_type"] == "skill"
        assert result["target"] == "evap_optimization"

    def test_classify_intent_reuse(self):
        """'回用调度' should route to skill (reuse_scheduling)."""
        result = self.agent.classify_intent("回用调度")
        assert result["route_type"] == "skill"
        assert result["target"] == "reuse_scheduling"

    def test_classify_intent_dispatch(self):
        """'全局调度' should route to skill (global_dispatch)."""
        result = self.agent.classify_intent("全局调度")
        assert result["route_type"] == "skill"
        assert result["target"] == "global_dispatch"

    def test_classify_intent_daily_report(self):
        """'日报' should route to skill (daily_report)."""
        result = self.agent.classify_intent("日报")
        assert result["route_type"] == "skill"
        assert result["target"] == "daily_report"

    # ------------------------------------------------------------------
    # Skill loading verification
    # ------------------------------------------------------------------

    def test_new_skills_loaded(self):
        """_skill_instances should contain all new Phase 3 skills."""
        expected_new_skills = [
            "leak_diagnosis",
            "evap_optimization",
            "reuse_scheduling",
            "global_dispatch",
            "daily_report",
        ]
        for skill_name in expected_new_skills:
            assert skill_name in self.agent._skill_instances, (
                f"Skill '{skill_name}' not found in _skill_instances. "
                f"Available: {list(self.agent._skill_instances.keys())}"
            )
