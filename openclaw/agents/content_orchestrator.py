"""ContentOrchestratorAgent — orchestrates the full content production pipeline.
内容编排Agent — 编排完整的内容生产流水线。

Pipeline: Planning → Writing → Review → Illustration → Publishing → Video/PPT
使用多Agent协同完成内容全流程：规划→写作→审查→配图→发布→视频/PPT
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent
from agents.message import AgentMessage, MessageType
from openclaw.agents.content_planner import ContentPlannerAgent
from openclaw.agents.content_publisher import ContentPublisherAgent
from openclaw.agents.content_reviewer import ContentReviewerAgent
from openclaw.models import (
    ArticleConfig,
    ContentPipeline,
    ContentStage,
    ImageConfig,
    PublishConfig,
    VideoConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a full pipeline run. / 流水线运行结果。"""

    pipeline_id: str = ""
    success: bool = False
    pipeline: ContentPipeline = field(default_factory=ContentPipeline)
    plan: dict = field(default_factory=dict)
    review: dict = field(default_factory=dict)
    publish_results: list[dict] = field(default_factory=list)
    execution_time: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "pipeline_id": self.pipeline_id,
            "success": self.success,
            "pipeline": self.pipeline.to_dict(),
            "plan": self.plan,
            "review": self.review,
            "publish_results": self.publish_results,
            "execution_time": self.execution_time,
            "error": self.error,
        }


class ContentOrchestratorAgent(BaseAgent):
    """Content Orchestrator — runs the full content production pipeline.
    内容编排Agent — 运行完整内容生产流水线。

    Coordinates:
    - ContentPlannerAgent: requirement analysis + planning
    - ContentReviewerAgent: quality review
    - ContentPublisherAgent: multi-channel publishing
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.planner = ContentPlannerAgent()
        self.reviewer = ContentReviewerAgent()
        self.publisher = ContentPublisherAgent()
        self._max_review_iterations = 3

    def get_capabilities(self) -> list[str]:
        return [
            "full_pipeline",
            "plan_only",
            "review_only",
            "multi_channel_publish",
            "iterative_refinement",
        ]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "run_full_pipeline")
        try:
            if action == "run_full_pipeline":
                result = self.run_full_pipeline(
                    requirement=message.content.get("requirement", ""),
                    content=message.content.get("content", ""),
                    article_config=message.content.get("article_config"),
                    image_config=message.content.get("image_config"),
                    publish_config=message.content.get("publish_config"),
                    video_config=message.content.get("video_config"),
                    channels=message.content.get("channels"),
                )
                return message.reply({"result": result})
            elif action == "plan_only":
                result = self.plan_only(message.content.get("requirement", ""))
                return message.reply({"result": result})
            elif action == "review_only":
                result = self.review_only(
                    message.content.get("content", ""),
                    message.content.get("config"),
                )
                return message.reply({"result": result})
            else:
                return message.error_reply(f"Unknown action: {action}")
        except Exception as exc:
            return message.error_reply(str(exc))

    def run_full_pipeline(
        self,
        requirement: str,
        content: str = "",
        article_config: dict | None = None,
        image_config: dict | None = None,
        publish_config: dict | None = None,
        video_config: dict | None = None,
        channels: list[str] | None = None,
    ) -> dict:
        """Run the full content production pipeline.
        运行完整内容生产流水线。

        Args:
            requirement: Free-text content requirement / 内容需求描述
            content: Optional pre-written content / 可选的已有内容
            article_config: Article configuration / 文章配置
            image_config: Image pipeline config / 图片配置
            publish_config: Publish config / 发布配置
            video_config: Video config / 视频配置
            channels: Override publish channels / 覆盖发布渠道

        Returns:
            Pipeline result dict.
        """
        start = time.time()
        pipeline_id = f"OC-{uuid.uuid4().hex[:8]}"

        pipeline = ContentPipeline(
            pipeline_id=pipeline_id,
            article=ArticleConfig(**(article_config or {})),
        )

        result = PipelineResult(
            pipeline_id=pipeline_id,
            pipeline=pipeline,
        )

        try:
            # Stage 1: Planning
            plan = self.planner.plan(requirement)
            pipeline.advance_stage(ContentStage.WRITING, {"plan": plan})
            result.plan = plan

            if channels:
                plan["publish_channels"] = channels

            # Stage 2: Writing (use provided content or generate placeholder)
            if content:
                article_content = content
            else:
                article_content = self._generate_placeholder_content(plan)
            pipeline.advance_stage(ContentStage.REVIEW, {"content_length": len(article_content)})

            # Stage 3: Review
            review = self.reviewer.review_article(article_content)
            pipeline.advance_stage(ContentStage.ILLUSTRATION, review.to_dict())
            result.review = review.to_dict()

            if not review.passed:
                logger.warning(
                    "Content review did not pass (score: %.0f), "
                    "continuing with warnings",
                    review.score,
                )

            # Stage 4: Illustration (if image_config provided)
            if image_config:
                img_review = self.reviewer.review_image_config(image_config)
                if img_review.passed:
                    ic = ImageConfig(**image_config)
                    img_result = self.publisher.publish_feishu_images(ic)
                    result.publish_results.append(img_result.to_dict())
                else:
                    pipeline.record_error(
                        "illustration",
                        f"Image config review failed: {img_review.summary}",
                    )

            pipeline.advance_stage(ContentStage.FEISHU_PUBLISH)

            # Stage 5: Publishing
            publish_channels = channels or plan.get("publish_channels", [])
            pub_plan = self.publisher.plan_publish(
                publish_channels,
                doc_token=publish_config.get("doc_token", "") if publish_config else "",
            )

            for stage in pub_plan:
                ch = stage["channel"]
                if ch == "wechat" and publish_config:
                    pc = PublishConfig(**{
                        k: v for k, v in publish_config.items()
                        if k in PublishConfig.__dataclass_fields__
                    })
                    pub_result = self.publisher.publish_wechat(pc)
                    result.publish_results.append(pub_result.to_dict())
                elif ch == "video" and video_config:
                    vc = VideoConfig(**{
                        k: v for k, v in video_config.items()
                        if k in VideoConfig.__dataclass_fields__
                    })
                    vid_result = self.publisher.generate_video(vc)
                    result.publish_results.append(vid_result.to_dict())

            pipeline.advance_stage(ContentStage.COMPLETED)
            result.success = True

        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            result.error = str(exc)
            pipeline.record_error(pipeline.current_stage.value, str(exc))

        result.execution_time = time.time() - start
        result.pipeline = pipeline
        return result.to_dict()

    def plan_only(self, requirement: str) -> dict:
        """Just run the planning stage. / 只运行规划阶段。"""
        return self.planner.plan(requirement)

    def review_only(self, content: str, config: dict | None = None) -> dict:
        """Just run the review stage. / 只运行审查阶段。"""
        return self.reviewer.review_article(content, config).to_dict()

    def _generate_placeholder_content(self, plan: dict) -> str:
        """Generate placeholder content from plan outline."""
        sections = plan.get("writing_outline", ["Introduction", "Body", "Conclusion"])
        title = plan.get("requirement", {}).get("title", "Untitled")
        lines = [f"# {title}\n"]
        for section in sections:
            lines.append(f"\n## {section}\n")
            lines.append(f"Content for section: {section}\n")
        return "\n".join(lines)
