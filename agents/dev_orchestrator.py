"""Development Orchestrator Agent — collaborative development pipeline.
开发编排 Agent — 协同开发流水线。

Coordinates the full software development lifecycle using multi-agent
collaboration: Planning → Development → Review → Testing.

Inspired by ChatDev / MetaGPT architectures, adapted for HydroMAS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from agents.base_agent import BaseAgent
from agents.dev_planner import DevPlannerAgent
from agents.dev_reviewer import DevReviewerAgent, ReviewResult
from agents.dev_tester import DevTesterAgent
from agents.message import AgentMessage, MessageType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline stage definitions
# ---------------------------------------------------------------------------

StageStatus = Literal[
    "pending", "in_progress", "completed", "failed", "skipped",
]


@dataclass
class PipelineStage:
    """A stage in the development pipeline. / 开发流水线的一个阶段。"""

    name: str
    agent: str
    status: StageStatus = "pending"
    result: dict = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "agent": self.agent,
            "status": self.status,
            "result": self.result,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class PipelineRun:
    """A complete pipeline execution record. / 完整流水线执行记录。"""

    id: str
    requirement: str
    stages: list[PipelineStage] = field(default_factory=list)
    status: StageStatus = "pending"
    created_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    completed_at: str = ""
    iteration: int = 1
    max_iterations: int = 3

    @property
    def current_stage(self) -> PipelineStage | None:
        for s in self.stages:
            if s.status == "in_progress":
                return s
        return None

    @property
    def all_passed(self) -> bool:
        return all(
            s.status in ("completed", "skipped") for s in self.stages
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "requirement": self.requirement,
            "status": self.status,
            "stages": [s.to_dict() for s in self.stages],
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# DevOrchestratorAgent
# ---------------------------------------------------------------------------

class DevOrchestratorAgent(BaseAgent):
    """Development Orchestrator — multi-agent collaborative pipeline.
    开发编排 Agent — 多智能体协同流水线。

    Pipeline stages:
    1. **Planning** (DevPlannerAgent): Requirement → Design Doc → Task DAG
    2. **Development** (Dev context): Execute tasks in DAG order
    3. **Review** (DevReviewerAgent): Architecture + Safety + Style review
    4. **Testing** (DevTesterAgent): Generate tests + validate coverage
    5. **Integration**: Merge results, update pipeline state

    Supports iterative refinement: if Review or Testing fails,
    loop back to Development (up to max_iterations).
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.planner = DevPlannerAgent()
        self.reviewer = DevReviewerAgent()
        self.tester = DevTesterAgent()
        self._run_counter = 0
        self._history: list[PipelineRun] = []

    def get_capabilities(self) -> list[str]:
        return [
            "dev_pipeline", "collaborative_dev", "planning",
            "review", "testing", "integration",
        ]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "run_full_pipeline")
        params = message.content.get("params", {})
        if action == "run_full_pipeline":
            result = self.run_full_pipeline(
                requirement=params.get("requirement", ""),
                files=params.get("files"),
                modules=params.get("modules"),
                scenario=params.get("scenario"),
                context=params.get("context"),
            )
            return message.reply(result)
        elif action == "create_pipeline":
            pipeline = self.create_pipeline(params.get("requirement", ""))
            return message.reply(pipeline.to_dict())
        else:
            return message.error_reply(f"Unknown dev_orchestrator action: {action}")

    def create_pipeline(self, requirement: str) -> PipelineRun:
        """Create a new development pipeline for a requirement.
        为需求创建新的开发流水线。

        Args:
            requirement: natural language development requirement

        Returns:
            PipelineRun with stages initialized.
        """
        self._run_counter += 1
        run = PipelineRun(
            id=f"DEV-{self._run_counter:04d}",
            requirement=requirement,
            stages=[
                PipelineStage("planning", "DevPlannerAgent"),
                PipelineStage("development", "DevCoder"),
                PipelineStage("review", "DevReviewerAgent"),
                PipelineStage("testing", "DevTesterAgent"),
                PipelineStage("integration", "DevOrchestrator"),
            ],
        )
        self._history.append(run)
        logger.info("DevOrchestrator: created pipeline %s", run.id)
        return run

    def run_planning(
        self, pipeline: PipelineRun, context: dict | None = None,
    ) -> dict:
        """Execute the planning stage.
        执行规划阶段。
        """
        stage = pipeline.stages[0]
        stage.status = "in_progress"
        stage.started_at = _now()

        design = self.planner.plan(pipeline.requirement, context)

        stage.result = design
        stage.status = "completed"
        stage.completed_at = _now()
        logger.info("DevOrchestrator: planning completed for %s", pipeline.id)
        return design

    def run_review(
        self,
        pipeline: PipelineRun,
        files: dict[str, str],
        context: dict | None = None,
    ) -> ReviewResult:
        """Execute the review stage.
        执行评审阶段。
        """
        stage = pipeline.stages[2]
        stage.status = "in_progress"
        stage.started_at = _now()

        # Review design doc from planning stage
        planning_result = pipeline.stages[0].result
        if planning_result:
            design_review = self.reviewer.review_design(planning_result)
            if not design_review.approved:
                stage.result = design_review.to_dict()
                stage.status = "failed"
                stage.completed_at = _now()
                return design_review

        # Review code files
        result = self.reviewer.review_code(files, context)

        stage.result = result.to_dict()
        stage.status = "completed" if result.approved else "failed"
        stage.completed_at = _now()
        logger.info(
            "DevOrchestrator: review %s for %s (approved=%s)",
            stage.status, pipeline.id, result.approved,
        )
        return result

    def run_testing(
        self,
        pipeline: PipelineRun,
        modules: list[str],
        scenario: str | None = None,
    ) -> dict:
        """Execute the testing stage.
        执行测试阶段。
        """
        stage = pipeline.stages[3]
        stage.status = "in_progress"
        stage.started_at = _now()

        suites: list[dict] = []
        for mod in modules:
            suite = self.tester.generate_test_suite(mod, scenario=scenario)
            suites.append(suite.to_dict())

        result = {
            "test_suites": suites,
            "total_cases": sum(s["test_count"] for s in suites),
            "modules_covered": modules,
            "scenario": scenario,
        }

        stage.result = result
        stage.status = "completed"
        stage.completed_at = _now()
        logger.info(
            "DevOrchestrator: testing completed, %d suites, %d cases",
            len(suites), result["total_cases"],
        )
        return result

    def run_integration(self, pipeline: PipelineRun) -> dict:
        """Execute the integration stage — aggregate results.
        执行集成阶段 — 汇总结果。
        """
        stage = pipeline.stages[4]
        stage.status = "in_progress"
        stage.started_at = _now()

        # Check if all prior stages passed
        prior_passed = all(
            s.status in ("completed", "skipped")
            for s in pipeline.stages[:4]
        )

        result = {
            "pipeline_id": pipeline.id,
            "requirement": pipeline.requirement,
            "all_stages_passed": prior_passed,
            "iteration": pipeline.iteration,
            "stage_summary": {
                s.name: s.status for s in pipeline.stages
            },
        }

        if prior_passed:
            pipeline.status = "completed"
            stage.status = "completed"
        else:
            # Check if we can iterate
            if pipeline.iteration < pipeline.max_iterations:
                pipeline.iteration += 1
                result["action"] = "iterate"
                result["message"] = (
                    f"Iteration {pipeline.iteration}: "
                    "re-running from development stage"
                )
                # Reset development, review, testing stages
                for s in pipeline.stages[1:4]:
                    s.status = "pending"
                    s.result = {}
                stage.status = "completed"
            else:
                pipeline.status = "failed"
                stage.status = "failed"
                result["action"] = "escalate"
                result["message"] = (
                    f"Max iterations ({pipeline.max_iterations}) reached, "
                    "escalating to human review"
                )

        stage.completed_at = _now()
        pipeline.completed_at = _now()
        logger.info(
            "DevOrchestrator: integration result for %s: %s",
            pipeline.id, result.get("action", "success"),
        )
        return result

    def run_full_pipeline(
        self,
        requirement: str,
        files: dict[str, str] | None = None,
        modules: list[str] | None = None,
        scenario: str | None = None,
        context: dict | None = None,
    ) -> dict:
        """Execute the complete development pipeline end-to-end.
        端到端执行完整开发流水线。

        Args:
            requirement: development requirement text
            files: code files to review (filepath → content)
            modules: modules to generate tests for
            scenario: scenario type (research/design/operations)
            context: additional context

        Returns:
            Complete pipeline execution report.
        """
        pipeline = self.create_pipeline(requirement)
        pipeline.status = "in_progress"

        # Stage 1: Planning
        design = self.run_planning(pipeline, context)

        # Stage 2: Development (mark as completed — actual coding is external)
        dev_stage = pipeline.stages[1]
        dev_stage.status = "completed"
        dev_stage.started_at = _now()
        dev_stage.completed_at = _now()
        dev_stage.result = {"note": "Development handled by external process"}

        # Stage 3: Review
        review_result = None
        if files:
            review_result = self.run_review(pipeline, files, context)

        else:
            pipeline.stages[2].status = "skipped"
            pipeline.stages[2].result = {
                "note": "No files provided for review",
            }

        # Stage 4: Testing
        if modules:
            self.run_testing(pipeline, modules, scenario)
        else:
            # Infer modules from planning
            req = design.get("requirement", {})
            inferred = req.get("affected_modules", [])
            if inferred:
                self.run_testing(pipeline, inferred, scenario)
            else:
                pipeline.stages[3].status = "skipped"
                pipeline.stages[3].result = {
                    "note": "No modules identified for testing",
                }

        # Stage 5: Integration
        integration = self.run_integration(pipeline)

        return {
            "pipeline": pipeline.to_dict(),
            "design_doc": design,
            "review": review_result.to_dict() if review_result else None,
            "integration": integration,
        }

    def get_history(self) -> list[dict]:
        """Get pipeline execution history. / 获取流水线执行历史。"""
        return [run.to_dict() for run in self._history]

    def generate_dev_report(self, pipeline: PipelineRun) -> str:
        """Generate a Markdown development report.
        生成 Markdown 格式开发报告。
        """
        lines = [
            f"# Development Pipeline Report: {pipeline.id}",
            f"**Requirement**: {pipeline.requirement}",
            f"**Status**: {pipeline.status}",
            (
                f"**Created**: {pipeline.created_at}"
                f"  |  **Completed**: {pipeline.completed_at}"
            ),
            f"**Iteration**: {pipeline.iteration}/{pipeline.max_iterations}",
            "",
            "## Pipeline Stages",
            "",
            "| Stage | Agent | Status | Duration |",
            "|-------|-------|--------|----------|",
        ]

        for s in pipeline.stages:
            duration = (
                f"{s.duration_seconds:.1f}s" if s.duration_seconds else "—"
            )
            lines.append(
                f"| {s.name} | {s.agent} | {s.status} | {duration} |"
            )

        # Planning details
        planning = pipeline.stages[0]
        if planning.result:
            req = planning.result.get("requirement", {})
            lines.extend([
                "",
                "## Planning Summary",
                f"- **Category**: {req.get('category', 'N/A')}",
                f"- **Priority**: {req.get('priority', 'N/A')}",
                f"- **Complexity**: {req.get('estimated_complexity', 'N/A')}",
                (
                    "- **Affected Layers**: "
                    f"{', '.join(req.get('affected_layers', []))}"
                ),
                (
                    "- **Affected Modules**: "
                    f"{', '.join(req.get('affected_modules', []))}"
                ),
            ])

        # Review details
        review = pipeline.stages[2]
        if review.result and review.status != "skipped":
            lines.extend([
                "",
                "## Review Summary",
                f"- **Approved**: {review.result.get('approved', 'N/A')}",
                f"- **Errors**: {review.result.get('error_count', 0)}",
                f"- **Warnings**: {review.result.get('warning_count', 0)}",
            ])

        # Testing details
        testing = pipeline.stages[3]
        if testing.result and testing.status != "skipped":
            lines.extend([
                "",
                "## Testing Summary",
                (
                    f"- **Total Test Cases**: "
                    f"{testing.result.get('total_cases', 0)}"
                ),
                (
                    f"- **Modules**: "
                    f"{', '.join(testing.result.get('modules_covered', []))}"
                ),
            ])

        lines.append("")
        lines.append(
            f"*Report generated: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )
        return "\n".join(lines)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
