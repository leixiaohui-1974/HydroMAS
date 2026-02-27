"""Tests for ContentOrchestratorAgent."""

from __future__ import annotations

from openclaw.agents.content_orchestrator import ContentOrchestratorAgent

_SAMPLE_CONTENT = """# 从AI助手到水网大脑

## 引言

当Anthropic推出Claude Code CLI工具时，AI行业进入了新阶段。

## 技术演进

从Chat到Code再到协同工作，AI正经历三阶段进化。

## 水网类比

水网自主等级(WNAL)的L1到L5升级路径与AI演进惊人相似。

## 总结

平台+插件的范式在AI和水网领域都在快速演进。
"""


class TestFullPipeline:
    def setup_method(self):
        self.orchestrator = ContentOrchestratorAgent()

    def test_basic_pipeline(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="写一篇关于水网智能化的文章",
        )
        assert result["success"]
        assert result["pipeline_id"].startswith("OC-")
        assert "plan" in result
        assert "review" in result

    def test_pipeline_with_content(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="发布这篇文章",
            content=_SAMPLE_CONTENT,
        )
        assert result["success"]
        assert result["review"]["passed"]

    def test_pipeline_with_channels(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="写文章",
            channels=["feishu", "wechat"],
        )
        assert result["success"]
        plan_channels = result["plan"]["publish_channels"]
        assert "feishu" in plan_channels
        assert "wechat" in plan_channels

    def test_pipeline_with_image_config(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="写文章配图",
            image_config={
                "doc_token": "abc123",
                "images": [
                    {"filename": "test.png", "prompt": "A detailed diagram"},
                ],
            },
        )
        assert result["success"]
        assert len(result["publish_results"]) > 0

    def test_pipeline_with_video_config(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="写文章转视频",
            channels=["video"],
            video_config={
                "article_path": "/tmp/article.md",
                "output": "/tmp/video.mp4",
                "title": "Test Video",
            },
        )
        assert result["success"]
        vid_results = [
            r for r in result["publish_results"] if r["channel"] == "video"
        ]
        assert len(vid_results) == 1
        assert vid_results[0]["success"]

    def test_pipeline_with_wechat_config(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="发到公众号",
            channels=["wechat"],
            publish_config={"doc_token": "abc123", "title": "Test"},
        )
        assert result["success"]

    def test_pipeline_execution_time(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="写一篇文章",
        )
        assert result["execution_time"] > 0

    def test_pipeline_stages_completed(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="写一篇文章",
        )
        pipeline = result["pipeline"]
        assert pipeline["current_stage"] == "completed"
        assert len(pipeline["stages_completed"]) > 0

    def test_pipeline_with_bad_image_config(self):
        result = self.orchestrator.run_full_pipeline(
            requirement="写文章",
            image_config={"images": []},  # Invalid: no images
        )
        # Pipeline still succeeds, but errors are recorded
        assert result["success"]
        pipeline = result["pipeline"]
        assert len(pipeline["errors"]) > 0


class TestPlanOnly:
    def test_plan_only(self):
        orchestrator = ContentOrchestratorAgent()
        plan = orchestrator.plan_only("写一篇AI技术文章")
        assert "plan_id" in plan
        assert "writing_outline" in plan
        assert len(plan["writing_outline"]) > 0


class TestReviewOnly:
    def test_review_good_content(self):
        orchestrator = ContentOrchestratorAgent()
        review = orchestrator.review_only(_SAMPLE_CONTENT)
        assert review["passed"]
        assert review["score"] > 0

    def test_review_bad_content(self):
        orchestrator = ContentOrchestratorAgent()
        review = orchestrator.review_only("x")
        assert review["score"] < 100
