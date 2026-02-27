"""ContentPipelineSkill — multi-agent content production pipeline as a HydroMAS skill.
内容流水线技能 — 以HydroMAS技能形式提供的多Agent内容生产流水线。
"""

from __future__ import annotations

import logging
import time

from skills.base_skill import BaseSkill, SkillMetadata, SkillResult

logger = logging.getLogger(__name__)


class ContentPipelineSkill(BaseSkill):
    """Content Pipeline Skill — orchestrate content production.
    内容流水线技能 — 编排内容生产。

    Pipeline:
    1. Planning: Analyse requirement → Content plan
    2. Writing: Generate or accept content
    3. Review: Quality check (structure, style, technical, compliance)
    4. Illustration: Image pipeline (Gemini → Feishu)
    5. Publishing: Feishu → WeChat → Video → PPT
    """

    _DEFAULT_METADATA = SkillMetadata(
        name="content_pipeline",
        display_name="内容流水线 / Content Pipeline",
        description=(
            "Multi-agent content production pipeline. "
            "Planning→Writing→Review→Publishing with multi-channel delivery. "
            "多Agent内容生产流水线：规划→写作→审查→发布，支持多渠道分发。"
        ),
        trigger_phrases=[
            "内容流水线", "写文章", "发布文章", "content pipeline",
            "write article", "publish content", "生成视频",
            "公众号发布", "配图", "全套发布",
        ],
        input_schema={
            "requirement": {"type": "string", "description": "Content requirement"},
            "content": {
                "type": "string",
                "description": "Pre-written content (optional)",
                "optional": True,
            },
            "channels": {
                "type": "array",
                "description": "Publish channels: feishu, wechat, video, ppt",
                "optional": True,
            },
            "image_config": {
                "type": "object",
                "description": "Image pipeline config",
                "optional": True,
            },
            "publish_config": {
                "type": "object",
                "description": "Publish config",
                "optional": True,
            },
            "video_config": {
                "type": "object",
                "description": "Video config",
                "optional": True,
            },
        },
        output_schema={
            "pipeline": {"type": "object"},
            "plan": {"type": "object"},
            "review": {"type": "object"},
            "publish_results": {"type": "array"},
        },
        tools_required=[],
        max_execution_time=600,
    )

    def __init__(self) -> None:
        super().__init__(metadata=self._DEFAULT_METADATA)

    async def execute(self, params: dict) -> SkillResult:
        """Execute the content production pipeline."""
        start = time.time()
        steps: list[str] = []

        requirement = params.get("requirement", "")
        if not requirement:
            return SkillResult(
                success=False,
                error="Missing 'requirement' parameter",
            )

        try:
            from openclaw.agents.content_orchestrator import ContentOrchestratorAgent

            orchestrator = ContentOrchestratorAgent()

            result = orchestrator.run_full_pipeline(
                requirement=requirement,
                content=params.get("content", ""),
                article_config=params.get("article_config"),
                image_config=params.get("image_config"),
                publish_config=params.get("publish_config"),
                video_config=params.get("video_config"),
                channels=params.get("channels"),
            )

            steps.append("Planning completed")
            steps.append("Writing completed")
            steps.append("Review completed")
            steps.append("Publishing completed")

            return SkillResult(
                success=result.get("success", False),
                data=result,
                execution_time=time.time() - start,
                steps_completed=steps,
            )

        except Exception as exc:
            logger.exception("ContentPipelineSkill failed: %s", exc)
            return SkillResult(
                success=False,
                error=str(exc),
                execution_time=time.time() - start,
                steps_completed=steps,
            )
