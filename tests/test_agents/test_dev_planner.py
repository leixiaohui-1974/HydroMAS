"""Tests for DevPlannerAgent."""

from __future__ import annotations

from agents.dev_planner import DevPlannerAgent, RequirementSpec


class TestRequirementAnalysis:
    """Test requirement analysis."""

    def setup_method(self):
        self.planner = DevPlannerAgent()

    def test_feature_detection(self):
        req = self.planner.analyse_requirement(
            "Add a new evaporation model for red mud drying"
        )
        assert req.category == "feature"
        assert "evaporation" in req.affected_modules

    def test_bugfix_detection(self):
        req = self.planner.analyse_requirement(
            "修复水平衡计算的bug"
        )
        assert req.category == "bugfix"
        assert "water_balance" in req.affected_modules

    def test_refactor_detection(self):
        req = self.planner.analyse_requirement(
            "Refactor the simulation module for better performance"
        )
        assert req.category == "refactor"
        assert "simulation" in req.affected_modules

    def test_priority_detection(self):
        req = self.planner.analyse_requirement(
            "紧急修复ODD安全检测的错误"
        )
        assert req.priority == "critical"
        assert req.category == "bugfix"

    def test_complexity_estimation(self):
        # Simple: one module
        req1 = self.planner.analyse_requirement("Fix PID controller")
        assert req1.estimated_complexity in ("low", "medium")

        # Complex: multiple modules and layers
        req2 = self.planner.analyse_requirement(
            "Add leak detection GNN model with MCP server, "
            "skill workflow, and agent integration"
        )
        assert req2.estimated_complexity in ("medium", "high")

    def test_layer_inference(self):
        req = self.planner.analyse_requirement(
            "Add new MCP tool for evaporation calculation"
        )
        assert any("L2" in layer for layer in req.affected_layers)

    def test_module_identification_chinese(self):
        req = self.planner.analyse_requirement(
            "实现冷却塔蒸发量的Merkel模型计算"
        )
        assert "evaporation" in req.affected_modules

    def test_to_dict(self):
        req = RequirementSpec(
            title="Test requirement",
            description="Test description",
            category="feature",
            affected_layers=["L0"],
            affected_modules=["simulation"],
        )
        d = req.to_dict()
        assert d["title"] == "Test requirement"
        assert d["affected_layers"] == ["L0"]


class TestPlanGeneration:
    """Test plan generation."""

    def setup_method(self):
        self.planner = DevPlannerAgent()

    def test_bugfix_plan(self):
        req = self.planner.analyse_requirement("Fix water balance bug")
        design = self.planner.generate_plan(req)
        plan = design.implementation_plan
        assert len(plan.nodes) > 0
        assert any("review" in n.id for n in plan.nodes)

    def test_new_skill_plan(self):
        req = self.planner.analyse_requirement(
            "Create a new skill for pressure monitoring"
        )
        design = self.planner.generate_plan(req)
        plan = design.implementation_plan
        assert any("test" in n.id for n in plan.nodes)

    def test_new_agent_plan(self):
        req = self.planner.analyse_requirement(
            "Implement a new agent for cost optimization"
        )
        design = self.planner.generate_plan(req)
        plan = design.implementation_plan
        assert any("card" in n.id for n in plan.nodes)

    def test_plan_dag_valid(self):
        req = self.planner.analyse_requirement("Add simulation feature")
        design = self.planner.generate_plan(req)
        # Should not raise
        design.implementation_plan.validate_dag()

    def test_design_doc_completeness(self):
        req = self.planner.analyse_requirement("Add new ODD dimension")
        design = self.planner.generate_plan(req)
        d = design.to_dict()
        assert "requirement" in d
        assert "architecture_notes" in d
        assert "implementation_plan" in d
        assert "test_strategy" in d
        assert "risk_notes" in d

    def test_risk_assessment_high_complexity(self):
        req = RequirementSpec(
            title="Complex change",
            description="Complex change",
            estimated_complexity="high",
            affected_layers=["L0", "L2", "L3"],
            affected_modules=["detection"],
        )
        design = self.planner.generate_plan(req)
        assert "High complexity" in design.risk_notes
        assert "Cross-layer" in design.risk_notes

    def test_end_to_end_plan(self):
        result = self.planner.plan("实现新的泄漏检测算法")
        assert "requirement" in result
        assert "implementation_plan" in result
        tasks = result["implementation_plan"]["tasks"]
        assert len(tasks) > 0
