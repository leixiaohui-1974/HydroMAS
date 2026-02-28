"""ContentPublisherAgent — manages multi-channel content publishing.
内容发布Agent — 管理多渠道内容发布。

Handles publishing to:
- Feishu (document + images)
- WeChat Official Account
- Video generation
- PPT generation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent
from agents.message import AgentMessage, MessageType
from openclaw.models import (
    ContentStage,
    ImageConfig,
    PublishConfig,
    VideoConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    """Result of a publish operation. / 发布操作结果。"""

    channel: str
    success: bool = False
    url: str = ""
    file_path: str = ""
    details: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "success": self.success,
            "url": self.url,
            "file_path": self.file_path,
            "details": self.details,
            "error": self.error,
        }


class ContentPublisherAgent(BaseAgent):
    """Content Publisher Agent — orchestrates multi-channel publishing.
    内容发布Agent — 编排多渠道发布。
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._publish_history: list[PublishResult] = []

    def get_capabilities(self) -> list[str]:
        return [
            "publish_planning",
            "feishu_publish",
            "wechat_publish",
            "video_generation",
            "config_validation",
        ]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "plan_publish")
        try:
            if action == "plan_publish":
                result = self.plan_publish(
                    message.content.get("channels", []),
                    message.content.get("article_path", ""),
                    message.content.get("doc_token", ""),
                )
                return message.reply({"result": result})
            elif action == "validate_config":
                result = self.validate_config(
                    message.content.get("channel", ""),
                    message.content.get("config", {}),
                )
                return message.reply({"result": result})
            elif action == "publish_feishu_images":
                cfg = ImageConfig(**message.content.get("config", {}))
                result = self.publish_feishu_images(cfg)
                return message.reply({"result": result.to_dict()})
            elif action == "publish_wechat":
                cfg = PublishConfig(**{
                    k: v for k, v in message.content.get("config", {}).items()
                    if k in PublishConfig.__dataclass_fields__
                })
                result = self.publish_wechat(cfg)
                return message.reply({"result": result.to_dict()})
            elif action == "generate_video":
                cfg = VideoConfig(**{
                    k: v for k, v in message.content.get("config", {}).items()
                    if k in VideoConfig.__dataclass_fields__
                })
                result = self.generate_video(cfg)
                return message.reply({"result": result.to_dict()})
            elif action == "get_history":
                return message.reply({"result": self.get_publish_history()})
            else:
                return message.error_reply(f"Unknown action: {action}")
        except Exception as exc:
            return message.error_reply(str(exc))

    def plan_publish(
        self,
        channels: list[str],
        article_path: str = "",
        doc_token: str = "",
    ) -> list[dict]:
        """Plan publishing sequence. / 规划发布顺序。

        Standard sequence: images → feishu → wechat → video → ppt
        """
        stages = []
        ordered_channels = ["feishu", "wechat", "video", "ppt"]

        for ch in ordered_channels:
            if ch in channels:
                stage = {
                    "channel": ch,
                    "stage": self._channel_to_stage(ch).value,
                    "requires": [],
                    "config_needed": self._config_keys(ch),
                }
                if ch == "wechat":
                    stage["requires"] = ["feishu"]
                elif ch == "video":
                    stage["requires"] = []
                stages.append(stage)

        return stages

    def validate_config(self, channel: str, config: dict) -> list[str]:
        """Validate publish config for a channel."""
        issues = []

        if channel == "feishu":
            ic = ImageConfig(**{k: v for k, v in config.items()
                               if k in ImageConfig.__dataclass_fields__})
            issues = ic.validate()
        elif channel == "video":
            vc = VideoConfig(**{k: v for k, v in config.items()
                               if k in VideoConfig.__dataclass_fields__})
            issues = vc.validate()
        elif channel == "wechat":
            if not config.get("doc_token"):
                issues.append("doc_token required for WeChat publish")

        return issues

    def publish_feishu_images(self, config: ImageConfig) -> PublishResult:
        """Publish images to Feishu document (dry-run without API calls).
        发布图片到飞书文档（无API调用的干运行）。
        """
        issues = config.validate()
        if issues:
            return PublishResult(
                channel="feishu",
                success=False,
                error=f"Config validation failed: {'; '.join(issues)}",
            )

        result = PublishResult(
            channel="feishu",
            success=True,
            details={
                "doc_token": config.doc_token,
                "n_images": len(config.images),
                "resolution": config.resolution,
                "image_filenames": [img.get("filename", "") for img in config.images],
            },
        )
        self._publish_history.append(result)
        return result

    def publish_wechat(self, config: PublishConfig) -> PublishResult:
        """Publish to WeChat (dry-run). / 发布到微信（干运行）。"""
        if not config.doc_token:
            return PublishResult(
                channel="wechat",
                success=False,
                error="doc_token required",
            )

        result = PublishResult(
            channel="wechat",
            success=True,
            details={
                "title": config.title,
                "author": config.author,
                "auto_publish": config.auto_publish,
                "mode": "draft" if not config.auto_publish else "published",
            },
        )
        self._publish_history.append(result)
        return result

    def generate_video(self, config: VideoConfig) -> PublishResult:
        """Generate video (dry-run). / 生成视频（干运行）。"""
        issues = config.validate()
        if issues:
            return PublishResult(
                channel="video",
                success=False,
                error=f"Config validation failed: {'; '.join(issues)}",
            )

        result = PublishResult(
            channel="video",
            success=True,
            file_path=config.output,
            details={
                "article_path": config.article_path,
                "voice": config.voice,
                "title": config.title,
            },
        )
        self._publish_history.append(result)
        return result

    def get_publish_history(self) -> list[dict]:
        """Get publish history."""
        return [r.to_dict() for r in self._publish_history]

    def _channel_to_stage(self, channel: str) -> ContentStage:
        return {
            "feishu": ContentStage.FEISHU_PUBLISH,
            "wechat": ContentStage.WECHAT_PUBLISH,
            "video": ContentStage.VIDEO,
            "ppt": ContentStage.PPT,
        }.get(channel, ContentStage.COMPLETED)

    def _config_keys(self, channel: str) -> list[str]:
        return {
            "feishu": ["doc_token", "images", "feishu_app_id"],
            "wechat": ["doc_token", "wechat_app_id"],
            "video": ["article_path", "output", "voice"],
            "ppt": ["article_content"],
        }.get(channel, [])
