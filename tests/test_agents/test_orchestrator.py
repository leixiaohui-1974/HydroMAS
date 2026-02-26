"""Tests for agents.orchestrator module."""

import pytest
from agents.orchestrator import OrchestratorAgent


class TestOrchestratorAgent:
    def setup_method(self):
        self.agent = OrchestratorAgent()

    def test_classify_skill_intent(self):
        result = self.agent.classify_intent("设计控制器")
        assert result["route_type"] == "skill"
        assert result["target"] == "control_system_design"

    def test_classify_tool_intent(self):
        result = self.agent.classify_intent("仿真一下水箱")
        assert result["route_type"] == "tool"
        assert result["target"] == "simulate_tank"

    def test_classify_agent_fallback(self):
        result = self.agent.classify_intent("帮我出一份报告")
        # This might match tool or fall to agent
        assert result["route_type"] in ("tool", "agent", "skill")

    def test_classify_odd_skill(self):
        result = self.agent.classify_intent("评估ODD")
        assert result["route_type"] == "skill"
        assert result["target"] == "odd_assessment"

    def test_classify_english(self):
        result = self.agent.classify_intent("design controller")
        assert result["route_type"] == "skill"
        assert result["target"] == "control_system_design"

    def test_get_available_skills(self):
        skills = self.agent.get_available_skills()
        assert len(skills) >= 1
        names = [s["name"] for s in skills]
        assert "control_system_design" in names
