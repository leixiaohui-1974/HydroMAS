"""Tests for DevOrchestratorAgent."""

from __future__ import annotations

from agents.dev_orchestrator import DevOrchestratorAgent, PipelineRun, PipelineStage


class TestPipelineCreation:
    """Test pipeline creation."""

    def setup_method(self):
        self.orch = DevOrchestratorAgent()

    def test_create_pipeline(self):
        pipeline = self.orch.create_pipeline("Add new feature")
        assert pipeline.id.startswith("DEV-")
        assert pipeline.requirement == "Add new feature"
        assert len(pipeline.stages) == 5
        assert pipeline.status == "pending"

    def test_pipeline_stages_order(self):
        pipeline = self.orch.create_pipeline("Test requirement")
        stage_names = [s.name for s in pipeline.stages]
        assert stage_names == [
            "planning", "development", "review",
            "testing", "integration",
        ]

    def test_pipeline_id_increments(self):
        p1 = self.orch.create_pipeline("First")
        p2 = self.orch.create_pipeline("Second")
        id1 = int(p1.id.split("-")[1])
        id2 = int(p2.id.split("-")[1])
        assert id2 == id1 + 1


class TestPlanningStage:
    """Test planning stage execution."""

    def setup_method(self):
        self.orch = DevOrchestratorAgent()

    def test_run_planning(self):
        pipeline = self.orch.create_pipeline(
            "Add Merkel evaporation model"
        )
        design = self.orch.run_planning(pipeline)
        assert pipeline.stages[0].status == "completed"
        assert "requirement" in design
        assert "implementation_plan" in design

    def test_planning_identifies_modules(self):
        pipeline = self.orch.create_pipeline(
            "实现新的泄漏检测GNN模型"
        )
        design = self.orch.run_planning(pipeline)
        req = design["requirement"]
        assert "detection" in req["affected_modules"]


class TestReviewStage:
    """Test review stage execution."""

    def setup_method(self):
        self.orch = DevOrchestratorAgent()

    def test_review_clean_code(self):
        pipeline = self.orch.create_pipeline("Test review")
        self.orch.run_planning(pipeline)

        files = {
            "core/new_module.py": (
                '"""New module."""\n'
                '\n'
                'def calculate(x):\n'
                '    """Calculate."""\n'
                '    return x * 2\n'
            ),
        }
        result = self.orch.run_review(pipeline, files)
        assert result.approved
        assert pipeline.stages[2].status == "completed"

    def test_review_bad_code(self):
        pipeline = self.orch.create_pipeline("Test bad review")
        self.orch.run_planning(pipeline)

        files = {
            "core/bad.py": (
                "from agents.orchestrator import OrchestratorAgent\n"
                "password = 'secret123'\n"
            ),
        }
        result = self.orch.run_review(pipeline, files)
        assert not result.approved
        assert pipeline.stages[2].status == "failed"


class TestTestingStage:
    """Test testing stage execution."""

    def setup_method(self):
        self.orch = DevOrchestratorAgent()

    def test_run_testing(self):
        pipeline = self.orch.create_pipeline("Test testing")
        result = self.orch.run_testing(
            pipeline,
            modules=["simulation", "control"],
        )
        assert pipeline.stages[3].status == "completed"
        assert result["total_cases"] > 0
        assert "simulation" in result["modules_covered"]

    def test_testing_with_scenario(self):
        pipeline = self.orch.create_pipeline("Test with scenario")
        result = self.orch.run_testing(
            pipeline,
            modules=["water_balance"],
            scenario="research",
        )
        assert result["scenario"] == "research"
        assert result["total_cases"] > 0


class TestIntegrationStage:
    """Test integration stage execution."""

    def setup_method(self):
        self.orch = DevOrchestratorAgent()

    def test_all_passed_integration(self):
        pipeline = self.orch.create_pipeline("Integration test")
        # Mark all stages as completed
        for s in pipeline.stages[:4]:
            s.status = "completed"

        result = self.orch.run_integration(pipeline)
        assert result["all_stages_passed"]
        assert pipeline.status == "completed"

    def test_failed_stage_triggers_iteration(self):
        pipeline = self.orch.create_pipeline("Iteration test")
        pipeline.stages[0].status = "completed"
        pipeline.stages[1].status = "completed"
        pipeline.stages[2].status = "failed"  # Review failed
        pipeline.stages[3].status = "completed"

        result = self.orch.run_integration(pipeline)
        assert not result["all_stages_passed"]
        assert result["action"] == "iterate"
        assert pipeline.iteration == 2

    def test_max_iterations_escalates(self):
        pipeline = self.orch.create_pipeline("Max iteration test")
        pipeline.iteration = 3
        pipeline.max_iterations = 3
        pipeline.stages[0].status = "completed"
        pipeline.stages[1].status = "completed"
        pipeline.stages[2].status = "failed"
        pipeline.stages[3].status = "completed"

        result = self.orch.run_integration(pipeline)
        assert result["action"] == "escalate"
        assert pipeline.status == "failed"


class TestFullPipeline:
    """Test end-to-end pipeline execution."""

    def setup_method(self):
        self.orch = DevOrchestratorAgent()

    def test_full_pipeline_with_files(self):
        result = self.orch.run_full_pipeline(
            requirement="Add new water balance node type",
            files={
                "core/water_balance/new_node.py": (
                    '"""New node type."""\n'
                    'def new_node():\n'
                    '    """Create new node."""\n'
                    '    return {}\n'
                ),
            },
            modules=["water_balance"],
        )
        assert "pipeline" in result
        assert "design_doc" in result
        assert result["pipeline"]["status"] in (
            "completed", "failed",
        )

    def test_full_pipeline_minimal(self):
        result = self.orch.run_full_pipeline(
            requirement="Simple change to simulation"
        )
        assert "pipeline" in result
        assert result["pipeline"]["id"].startswith("DEV-")

    def test_full_pipeline_with_scenario(self):
        result = self.orch.run_full_pipeline(
            requirement="Add evaporation optimization",
            modules=["evaporation"],
            scenario="research",
        )
        assert "pipeline" in result

    def test_history_tracking(self):
        self.orch.run_full_pipeline(requirement="Task 1")
        self.orch.run_full_pipeline(requirement="Task 2")
        history = self.orch.get_history()
        assert len(history) >= 2


class TestReportGeneration:
    """Test development report generation."""

    def setup_method(self):
        self.orch = DevOrchestratorAgent()

    def test_generate_report(self):
        pipeline = self.orch.create_pipeline("Report test")
        self.orch.run_planning(pipeline)

        report = self.orch.generate_dev_report(pipeline)
        assert "# Development Pipeline Report" in report
        assert pipeline.id in report
        assert "Planning Summary" in report
        assert "| Stage |" in report


class TestDataClasses:
    """Test pipeline data classes."""

    def test_pipeline_stage_to_dict(self):
        stage = PipelineStage(
            name="planning",
            agent="DevPlannerAgent",
            status="completed",
        )
        d = stage.to_dict()
        assert d["name"] == "planning"
        assert d["status"] == "completed"

    def test_pipeline_run_current_stage(self):
        run = PipelineRun(id="DEV-001", requirement="Test")
        run.stages = [
            PipelineStage("a", "X", status="completed"),
            PipelineStage("b", "Y", status="in_progress"),
        ]
        assert run.current_stage is not None
        assert run.current_stage.name == "b"

    def test_pipeline_run_all_passed(self):
        run = PipelineRun(id="DEV-001", requirement="Test")
        run.stages = [
            PipelineStage("a", "X", status="completed"),
            PipelineStage("b", "Y", status="skipped"),
        ]
        assert run.all_passed

    def test_pipeline_run_not_all_passed(self):
        run = PipelineRun(id="DEV-001", requirement="Test")
        run.stages = [
            PipelineStage("a", "X", status="completed"),
            PipelineStage("b", "Y", status="failed"),
        ]
        assert not run.all_passed
