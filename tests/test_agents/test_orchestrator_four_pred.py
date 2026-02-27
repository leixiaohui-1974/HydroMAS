"""Tests for orchestrator routing to 四预 Skills."""

from agents.orchestrator import OrchestratorAgent


class TestFourPredictionRouting:
    def setup_method(self):
        self.agent = OrchestratorAgent()

    def test_forecast_routing(self):
        result = self.agent.classify_intent("未来一小时水位会怎么变")
        assert result["route_type"] == "skill"
        assert result["target"] == "forecast_skill"

    def test_warning_routing(self):
        result = self.agent.classify_intent("现在安不安全？")
        assert result["route_type"] == "skill"
        assert result["target"] == "warning_skill"

    def test_rehearsal_routing(self):
        result = self.agent.classify_intent("方案对比推演")
        assert result["route_type"] == "skill"
        assert result["target"] == "rehearsal_skill"

    def test_plan_routing(self):
        result = self.agent.classify_intent("给我出一套应急方案")
        assert result["route_type"] == "skill"
        assert result["target"] == "plan_skill"

    def test_four_prediction_loop_routing(self):
        result = self.agent.classify_intent("一键四预")
        assert result["route_type"] == "skill"
        assert result["target"] == "four_prediction_loop"

    def test_english_forecast(self):
        result = self.agent.classify_intent("forecast water level")
        assert result["route_type"] == "skill"
        assert result["target"] == "forecast_skill"

    def test_english_what_if(self):
        result = self.agent.classify_intent("what if inflow increases?")
        assert result["route_type"] == "skill"
        assert result["target"] == "rehearsal_skill"

    def test_all_ten_skills_loaded(self):
        skills = self.agent.get_available_skills()
        names = {s["name"] for s in skills}
        expected = {
            "control_system_design", "data_analysis_predict",
            "odd_assessment", "optimization_design", "full_lifecycle",
            "forecast_skill", "warning_skill", "rehearsal_skill",
            "plan_skill", "four_prediction_loop",
        }
        assert expected.issubset(names), f"Missing: {expected - names}"
