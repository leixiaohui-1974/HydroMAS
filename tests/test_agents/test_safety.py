"""Tests for agents.safety_agent module."""

from agents.safety_agent import SafetyAgent


class TestSafetyAgent:
    def setup_method(self):
        self.agent = SafetyAgent()

    def test_check_normal_state(self):
        result = self.agent.check_state({"water_level": 1.0})
        assert result["zone"] == "normal"

    def test_check_mrc_state(self):
        result = self.agent.check_state({"water_level": 2.5})
        assert result["zone"] == "mrc"

    def test_check_action_safe(self):
        result = self.agent.check_action_safe(
            action={"type": "set_inflow", "value": 0.03},
            current_state={"water_level": 1.0},
        )
        assert result["safe"] is True
        assert result["zone"] == "normal"

    def test_check_action_mrc(self):
        result = self.agent.check_action_safe(
            action={"type": "set_inflow", "value": 0.05},
            current_state={"water_level": 2.0},
        )
        assert result["safe"] is False
        assert result["zone"] == "mrc"

    def test_violation_log(self):
        self.agent.check_state({"water_level": 2.5})
        log = self.agent.get_violation_log()
        assert len(log) == 1
        self.agent.clear_violation_log()
        assert len(self.agent.get_violation_log()) == 0

    def test_monitor_series(self):
        states = [
            {"water_level": 1.0},
            {"water_level": 1.5},
            {"water_level": 2.0},
        ]
        result = self.agent.monitor_series(states, [0, 1, 2])
        assert result["worst_zone"] == "mrc"
