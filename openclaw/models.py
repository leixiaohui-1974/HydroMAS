"""Data models for OpenClaw content pipeline.
OpenClaw 内容流水线数据模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContentStage(str, Enum):
    """Content production pipeline stages. / 内容生产流水线阶段。"""

    PLANNING = "planning"
    WRITING = "writing"
    REVIEW = "review"
    ILLUSTRATION = "illustration"
    FEISHU_PUBLISH = "feishu_publish"
    WECHAT_PUBLISH = "wechat_publish"
    VIDEO = "video"
    PPT = "ppt"
    COMPLETED = "completed"


@dataclass
class ArticleConfig:
    """Configuration for an article. / 文章配置。"""

    title: str = ""
    author: str = "雷晓辉"
    topic: str = ""
    style: str = "technical"  # technical, popular_science, academic
    language: str = "zh"
    target_length: int = 2000  # characters
    keywords: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "author": self.author,
            "topic": self.topic,
            "style": self.style,
            "language": self.language,
            "target_length": self.target_length,
            "keywords": self.keywords,
            "references": self.references,
        }


@dataclass
class ImageConfig:
    """Configuration for image generation pipeline. / 图片生成配置。"""

    doc_token: str = ""
    output_dir: str = ""
    resolution: str = "2K"
    images: list[dict] = field(default_factory=list)
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    gemini_api_key: str = ""

    def to_pipeline_config(self) -> dict:
        """Convert to pipeline JSON config format."""
        return {
            "feishu": {
                "app_id": self.feishu_app_id,
                "app_secret": self.feishu_app_secret,
            },
            "doc_token": self.doc_token,
            "gemini_api_key": self.gemini_api_key,
            "output_dir": self.output_dir,
            "resolution": self.resolution,
            "images": self.images,
        }

    def validate(self) -> list[str]:
        """Validate configuration, return list of issues."""
        issues = []
        if not self.doc_token:
            issues.append("doc_token is required")
        if not self.images:
            issues.append("At least one image is required")
        for i, img in enumerate(self.images):
            if "filename" not in img:
                issues.append(f"Image {i}: missing filename")
            if "prompt" not in img:
                issues.append(f"Image {i}: missing prompt")
        return issues


@dataclass
class PublishConfig:
    """Configuration for WeChat publishing. / 微信发布配置。"""

    doc_token: str = ""
    title: str = ""
    author: str = "雷晓辉"
    auto_publish: bool = False
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    def to_pipeline_config(self) -> dict:
        return {
            "feishu": {
                "app_id": self.feishu_app_id,
                "app_secret": self.feishu_app_secret,
            },
            "wechat": {
                "app_id": self.wechat_app_id,
                "app_secret": self.wechat_app_secret,
            },
            "doc_token": self.doc_token,
            "title": self.title,
            "author": self.author,
            "auto_publish": self.auto_publish,
        }


@dataclass
class VideoConfig:
    """Configuration for article-to-video pipeline. / 视频生成配置。"""

    article_path: str = ""
    images_dir: str = ""
    output: str = ""
    voice: str = "zh-CN-YunxiNeural"
    rate: str = "+0%"
    title: str = ""

    AVAILABLE_VOICES = {
        "zh-CN-YunxiNeural": "男-标准讲述",
        "zh-CN-YunyangNeural": "男-专业新闻",
        "zh-CN-XiaoxiaoNeural": "女-温暖对话",
        "zh-CN-XiaoyiNeural": "女-年轻活力",
    }

    def to_pipeline_config(self) -> dict:
        return {
            "article_path": self.article_path,
            "images_dir": self.images_dir,
            "output": self.output,
            "voice": self.voice,
            "rate": self.rate,
            "title": self.title,
        }

    def validate(self) -> list[str]:
        issues = []
        if not self.article_path:
            issues.append("article_path is required")
        if not self.output:
            issues.append("output path is required")
        if self.voice not in self.AVAILABLE_VOICES:
            issues.append(
                f"Unknown voice '{self.voice}', "
                f"available: {list(self.AVAILABLE_VOICES.keys())}"
            )
        return issues


@dataclass
class ContentPipeline:
    """A content production pipeline run. / 内容生产流水线运行记录。"""

    pipeline_id: str = ""
    article: ArticleConfig = field(default_factory=ArticleConfig)
    current_stage: ContentStage = ContentStage.PLANNING
    stages_completed: list[str] = field(default_factory=list)
    stage_results: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def is_completed(self) -> bool:
        return self.current_stage == ContentStage.COMPLETED

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def advance_stage(self, stage: ContentStage, result: dict | None = None) -> None:
        """Mark a stage as completed and advance."""
        self.stages_completed.append(self.current_stage.value)
        if result:
            self.stage_results[self.current_stage.value] = result
        self.current_stage = stage

    def record_error(self, stage: str, error: str) -> None:
        self.errors.append(f"[{stage}] {error}")

    def to_dict(self) -> dict:
        return {
            "pipeline_id": self.pipeline_id,
            "article": self.article.to_dict(),
            "current_stage": self.current_stage.value,
            "stages_completed": self.stages_completed,
            "stage_results": self.stage_results,
            "errors": self.errors,
            "is_completed": self.is_completed,
        }
