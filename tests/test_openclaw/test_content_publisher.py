"""Tests for ContentPublisherAgent."""

from __future__ import annotations

from openclaw.agents.content_publisher import (
    ContentPublisherAgent,
    PublishResult,
)
from openclaw.models import ImageConfig, PublishConfig, VideoConfig


class TestPublishPlanning:
    def setup_method(self):
        self.publisher = ContentPublisherAgent()

    def test_plan_all_channels(self):
        plan = self.publisher.plan_publish(
            ["feishu", "wechat", "video", "ppt"],
        )
        channels = [s["channel"] for s in plan]
        assert "feishu" in channels
        assert "wechat" in channels
        assert "video" in channels
        assert "ppt" in channels

    def test_plan_preserves_order(self):
        plan = self.publisher.plan_publish(["video", "feishu", "wechat"])
        channels = [s["channel"] for s in plan]
        # feishu should come before wechat
        assert channels.index("feishu") < channels.index("wechat")

    def test_wechat_requires_feishu(self):
        plan = self.publisher.plan_publish(["feishu", "wechat"])
        wechat_stage = next(s for s in plan if s["channel"] == "wechat")
        assert "feishu" in wechat_stage["requires"]

    def test_config_needed(self):
        plan = self.publisher.plan_publish(["feishu"])
        assert "doc_token" in plan[0]["config_needed"]


class TestFeishuPublish:
    def setup_method(self):
        self.publisher = ContentPublisherAgent()

    def test_publish_feishu_images_success(self):
        ic = ImageConfig(
            doc_token="abc123",
            images=[{"filename": "test.png", "prompt": "test"}],
        )
        result = self.publisher.publish_feishu_images(ic)
        assert result.success
        assert result.channel == "feishu"
        assert result.details["n_images"] == 1

    def test_publish_feishu_images_invalid(self):
        ic = ImageConfig()  # no doc_token, no images
        result = self.publisher.publish_feishu_images(ic)
        assert not result.success
        assert "validation" in result.error.lower()


class TestWeChatPublish:
    def setup_method(self):
        self.publisher = ContentPublisherAgent()

    def test_publish_wechat_draft(self):
        pc = PublishConfig(doc_token="abc", title="Test Article")
        result = self.publisher.publish_wechat(pc)
        assert result.success
        assert result.details["mode"] == "draft"

    def test_publish_wechat_auto(self):
        pc = PublishConfig(doc_token="abc", auto_publish=True)
        result = self.publisher.publish_wechat(pc)
        assert result.success
        assert result.details["mode"] == "published"

    def test_publish_wechat_no_token(self):
        pc = PublishConfig()
        result = self.publisher.publish_wechat(pc)
        assert not result.success


class TestVideoGeneration:
    def setup_method(self):
        self.publisher = ContentPublisherAgent()

    def test_generate_video_success(self):
        vc = VideoConfig(
            article_path="/tmp/article.md",
            output="/tmp/video.mp4",
            title="Test",
        )
        result = self.publisher.generate_video(vc)
        assert result.success
        assert result.file_path == "/tmp/video.mp4"

    def test_generate_video_invalid(self):
        vc = VideoConfig()  # missing required fields
        result = self.publisher.generate_video(vc)
        assert not result.success


class TestPublishHistory:
    def test_history_tracked(self):
        publisher = ContentPublisherAgent()
        ic = ImageConfig(
            doc_token="abc",
            images=[{"filename": "f.png", "prompt": "test"}],
        )
        publisher.publish_feishu_images(ic)
        history = publisher.get_publish_history()
        assert len(history) == 1
        assert history[0]["channel"] == "feishu"

    def test_multiple_publishes(self):
        publisher = ContentPublisherAgent()
        ic = ImageConfig(
            doc_token="abc",
            images=[{"filename": "f.png", "prompt": "test"}],
        )
        pc = PublishConfig(doc_token="abc")
        publisher.publish_feishu_images(ic)
        publisher.publish_wechat(pc)
        assert len(publisher.get_publish_history()) == 2


class TestPublishResult:
    def test_to_dict(self):
        r = PublishResult(channel="feishu", success=True, url="https://example.com")
        d = r.to_dict()
        assert d["channel"] == "feishu"
        assert d["success"] is True
        assert d["url"] == "https://example.com"


class TestValidateConfig:
    def setup_method(self):
        self.publisher = ContentPublisherAgent()

    def test_validate_feishu_ok(self):
        issues = self.publisher.validate_config("feishu", {
            "doc_token": "abc",
            "images": [{"filename": "f.png", "prompt": "test"}],
        })
        assert len(issues) == 0

    def test_validate_video_missing_path(self):
        issues = self.publisher.validate_config("video", {
            "output": "/tmp/v.mp4",
        })
        assert any("article_path" in i for i in issues)
