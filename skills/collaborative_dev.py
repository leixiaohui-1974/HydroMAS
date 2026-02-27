"""Collaborative Development Skill — multi-agent dev pipeline.
协同开发技能 — 多智能体开发流水线。

Orchestrates a full Planning→Development→Review→Testing pipeline
using specialized development agents.

写作 + 建模 + 管理 = 科研 / MBD设计 / 运维
"""

from __future__ import annotations

import logging
import time

from skills.base_skill import BaseSkill, SkillMetadata, SkillResult

logger = logging.getLogger(__name__)


class CollaborativeDevSkill(BaseSkill):
    """Run a multi-agent collaborative development pipeline.
    运行多智能体协同开发流水线。

    Pipeline:
    1. Planning: Analyse requirement → Design doc → Task DAG
    2. Development: (External — code changes)
    3. Review: Architecture + Safety + Style + Domain checks
    4. Testing: Generate test suites + validate coverage
    5. Integration: Aggregate results, decide pass/iterate/escalate
    """

    _DEFAULT_METADATA = SkillMetadata(
        name="collaborative_dev",
        display_name="协同开发 / Collaborative Development",
        description=(
            "Multi-agent collaborative development pipeline. "
            "Planning→Development→Review→Testing with iterative refinement. "
            "多智能体协同开发流水线：规划→开发→评审→测试，支持迭代改进。"
        ),
        trigger_phrases=[
            "协同开发", "开发流水线", "collaborative dev",
            "dev pipeline", "规划开发评审测试",
            "plan develop review test",
        ],
        input_schema={
            "requirement": {"type": "string", "description": "Development requirement"},
            "files": {
                "type": "object",
                "description": "Code files to review (filepath→content)",
                "optional": True,
            },
            "modules": {
                "type": "array",
                "description": "Modules to test",
                "optional": True,
            },
            "scenario": {
                "type": "string",
                "enum": ["research", "design", "operations"],
                "optional": True,
            },
        },
        output_schema={
            "pipeline": {"type": "object"},
            "design_doc": {"type": "object"},
            "review": {"type": "object"},
            "integration": {"type": "object"},
        },
        tools_required=[],
        max_execution_time=300,
    )

    def __init__(self) -> None:
        super().__init__(metadata=self._DEFAULT_METADATA)

    async def execute(self, params: dict) -> SkillResult:
        """Execute the collaborative development pipeline.
        执行协同开发流水线。
        """
        start = time.time()
        steps: list[str] = []

        requirement = params.get("requirement", "")
        if not requirement:
            return SkillResult(
                success=False,
                error="Missing 'requirement' parameter",
            )

        try:
            # Lazy import to avoid circular dependencies
            from agents.dev_orchestrator import DevOrchestratorAgent

            orchestrator = DevOrchestratorAgent()

            # Run full pipeline
            result = orchestrator.run_full_pipeline(
                requirement=requirement,
                files=params.get("files"),
                modules=params.get("modules"),
                scenario=params.get("scenario"),
                context=params.get("context"),
            )

            steps.append("Pipeline created")
            steps.append("Planning completed")
            steps.append("Review completed")
            steps.append("Testing completed")
            steps.append("Integration completed")

            return SkillResult(
                success=True,
                data=result,
                execution_time=time.time() - start,
                steps_completed=steps,
            )

        except Exception as exc:
            logger.exception("CollaborativeDevSkill failed: %s", exc)
            return SkillResult(
                success=False,
                error=str(exc),
                execution_time=time.time() - start,
                steps_completed=steps,
            )
