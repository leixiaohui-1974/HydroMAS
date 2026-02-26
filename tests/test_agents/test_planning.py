"""Tests for agents.planning_agent module."""

import pytest
from agents.planning_agent import PlanningAgent, TaskPlan, TaskNode


class TestPlanningAgent:
    def setup_method(self):
        self.agent = PlanningAgent()

    def test_compare_controllers_plan(self):
        plan = self.agent.plan("比较PID和MPC哪个好")
        assert plan.objective == "Compare PID and MPC controllers"
        assert len(plan.nodes) >= 2

    def test_full_analysis_plan(self):
        plan = self.agent.plan("做一个完整分析")
        assert len(plan.nodes) >= 1

    def test_default_plan(self):
        plan = self.agent.plan("做点什么")
        assert len(plan.nodes) == 1


class TestTaskPlan:
    def test_get_ready_tasks(self):
        plan = TaskPlan()
        plan.add_node(TaskNode("a", "task a", "tool_a"))
        plan.add_node(TaskNode("b", "task b", "tool_b", dependencies=["a"]))

        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "a"

    def test_to_dict(self):
        plan = TaskPlan(objective="test")
        plan.add_node(TaskNode("a", "task a", "tool_a"))
        d = plan.to_dict()
        assert d["objective"] == "test"
        assert len(d["tasks"]) == 1
