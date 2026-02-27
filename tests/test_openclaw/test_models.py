"""Tests for OpenClaw data models."""

from __future__ import annotations

from openclaw.models import (
    ArticleConfig,
    ContentPipeline,
    ContentStage,
    ImageConfig,
    PublishConfig,
    VideoConfig,
)


class TestArticleConfig:
    def test_default_values(self):
        ac = ArticleConfig()
        assert ac.author == "雷晓辉"
        assert ac.language == "zh"
        assert ac.target_length == 2000

    def test_to_dict(self):
        ac = ArticleConfig(title="Test", topic="Water AI")
        d = ac.to_dict()
        assert d["title"] == "Test"
        assert d["topic"] == "Water AI"


class TestImageConfig:
    def test_to_pipeline_config(self):
        ic = ImageConfig(
            doc_token="abc123",
            output_dir="/tmp/images",
            images=[{"filename": "test.png", "prompt": "A diagram"}],
            feishu_app_id="app1",
        )
        config = ic.to_pipeline_config()
        assert config["doc_token"] == "abc123"
        assert config["feishu"]["app_id"] == "app1"
        assert len(config["images"]) == 1

    def test_validate_ok(self):
        ic = ImageConfig(
            doc_token="abc",
            images=[{"filename": "f.png", "prompt": "test"}],
        )
        assert ic.validate() == []

    def test_validate_missing_doc_token(self):
        ic = ImageConfig(images=[{"filename": "f.png", "prompt": "test"}])
        issues = ic.validate()
        assert any("doc_token" in i for i in issues)

    def test_validate_missing_images(self):
        ic = ImageConfig(doc_token="abc")
        issues = ic.validate()
        assert any("image" in i.lower() for i in issues)

    def test_validate_image_missing_prompt(self):
        ic = ImageConfig(doc_token="abc", images=[{"filename": "f.png"}])
        issues = ic.validate()
        assert any("prompt" in i for i in issues)


class TestVideoConfig:
    def test_to_pipeline_config(self):
        vc = VideoConfig(
            article_path="/tmp/article.md",
            output="/tmp/video.mp4",
            title="Test Video",
        )
        config = vc.to_pipeline_config()
        assert config["article_path"] == "/tmp/article.md"
        assert config["voice"] == "zh-CN-YunxiNeural"

    def test_validate_ok(self):
        vc = VideoConfig(article_path="/tmp/a.md", output="/tmp/v.mp4")
        assert vc.validate() == []

    def test_validate_missing_path(self):
        vc = VideoConfig(output="/tmp/v.mp4")
        issues = vc.validate()
        assert any("article_path" in i for i in issues)

    def test_validate_bad_voice(self):
        vc = VideoConfig(
            article_path="/a.md", output="/v.mp4", voice="bad-voice",
        )
        issues = vc.validate()
        assert any("voice" in i.lower() for i in issues)

    def test_available_voices(self):
        assert len(VideoConfig.AVAILABLE_VOICES) >= 4


class TestPublishConfig:
    def test_to_pipeline_config(self):
        pc = PublishConfig(doc_token="abc", title="Test")
        config = pc.to_pipeline_config()
        assert config["doc_token"] == "abc"
        assert config["auto_publish"] is False


class TestContentPipeline:
    def test_initial_state(self):
        p = ContentPipeline(pipeline_id="test-1")
        assert p.current_stage == ContentStage.PLANNING
        assert not p.is_completed
        assert not p.has_errors

    def test_advance_stage(self):
        p = ContentPipeline(pipeline_id="test-1")
        p.advance_stage(ContentStage.WRITING, {"plan": "done"})
        assert p.current_stage == ContentStage.WRITING
        assert "planning" in p.stages_completed
        assert "plan" in p.stage_results["planning"]

    def test_complete(self):
        p = ContentPipeline(pipeline_id="test-1")
        p.advance_stage(ContentStage.WRITING)
        p.advance_stage(ContentStage.REVIEW)
        p.advance_stage(ContentStage.COMPLETED)
        assert p.is_completed

    def test_record_error(self):
        p = ContentPipeline(pipeline_id="test-1")
        p.record_error("review", "Content too short")
        assert p.has_errors
        assert "Content too short" in p.errors[0]

    def test_to_dict(self):
        p = ContentPipeline(pipeline_id="test-1")
        d = p.to_dict()
        assert d["pipeline_id"] == "test-1"
        assert d["current_stage"] == "planning"
        assert d["is_completed"] is False


class TestContentStage:
    def test_all_stages_defined(self):
        expected = [
            "planning", "writing", "review", "illustration",
            "feishu_publish", "wechat_publish", "video", "ppt", "completed",
        ]
        actual = [s.value for s in ContentStage]
        for e in expected:
            assert e in actual
