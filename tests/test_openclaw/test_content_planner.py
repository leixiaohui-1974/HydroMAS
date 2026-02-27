"""Tests for ContentPlannerAgent."""

from __future__ import annotations

from openclaw.agents.content_planner import (
    ContentPlan,
    ContentPlannerAgent,
    ContentRequirement,
)


class TestRequirementAnalysis:
    def setup_method(self):
        self.planner = ContentPlannerAgent()

    def test_article_type_detection(self):
        req = self.planner.analyse_requirement("写一篇关于AI CLI工具的文章")
        assert req.content_type == "article"

    def test_report_type_detection(self):
        req = self.planner.analyse_requirement("生成本周水网运行日报")
        assert req.content_type == "report"

    def test_tutorial_type_detection(self):
        req = self.planner.analyse_requirement("写一个HydroMAS使用教程")
        assert req.content_type == "tutorial"

    def test_audience_technical(self):
        req = self.planner.analyse_requirement("写一篇水网AI技术架构文章")
        assert req.target_audience == "technical"

    def test_audience_academic(self):
        req = self.planner.analyse_requirement("写一篇关于WNAL的学术论文")
        assert req.target_audience == "academic"

    def test_audience_general(self):
        req = self.planner.analyse_requirement("写一篇AI科普入门文章")
        assert req.target_audience == "general"

    def test_channel_detection_wechat(self):
        req = self.planner.analyse_requirement("写一篇文章发到公众号")
        assert "wechat" in req.channels

    def test_channel_detection_video(self):
        req = self.planner.analyse_requirement("写文章并生成讲解视频")
        assert "video" in req.channels

    def test_default_channels(self):
        req = self.planner.analyse_requirement("写一篇文章")
        assert "feishu" in req.channels
        assert "wechat" in req.channels

    def test_priority_urgent(self):
        req = self.planner.analyse_requirement("紧急写一篇新闻稿")
        assert req.priority == "urgent"

    def test_priority_high(self):
        req = self.planner.analyse_requirement("重要：写一篇技术文章")
        assert req.priority == "high"

    def test_title_extraction(self):
        req = self.planner.analyse_requirement('写一篇《从AI助手到水网大脑》的文章')
        assert req.title == "从AI助手到水网大脑"

    def test_length_estimation_long(self):
        req = self.planner.analyse_requirement("写一篇详细的长文")
        assert req.estimated_length == 5000

    def test_length_estimation_short(self):
        req = self.planner.analyse_requirement("写一篇简要的短文")
        assert req.estimated_length == 1000


class TestPlanGeneration:
    def setup_method(self):
        self.planner = ContentPlannerAgent()

    def test_article_plan(self):
        req = self.planner.analyse_requirement("写一篇AI技术文章")
        plan = self.planner.generate_plan(req)
        assert isinstance(plan, ContentPlan)
        assert plan.plan_id.startswith("CP-")
        assert len(plan.writing_outline) > 0

    def test_report_plan_outline(self):
        req = ContentRequirement(content_type="report")
        plan = self.planner.generate_plan(req)
        assert any("概述" in section or "Overview" in section
                    for section in plan.writing_outline)

    def test_tutorial_plan_outline(self):
        req = ContentRequirement(content_type="tutorial")
        plan = self.planner.generate_plan(req)
        assert any("步骤" in section or "Step" in section
                    for section in plan.writing_outline)

    def test_image_plan_generated(self):
        req = self.planner.analyse_requirement("写一篇文章")
        plan = self.planner.generate_plan(req)
        assert len(plan.image_plan) >= 3

    def test_stages_include_review(self):
        req = self.planner.analyse_requirement("写一篇文章")
        plan = self.planner.generate_plan(req)
        assert "review" in plan.estimated_stages

    def test_stages_include_wechat(self):
        req = self.planner.analyse_requirement("写文章发公众号")
        plan = self.planner.generate_plan(req)
        assert "wechat_publish" in plan.estimated_stages

    def test_high_priority_note(self):
        req = ContentRequirement(priority="urgent")
        plan = self.planner.generate_plan(req)
        assert "priority" in plan.notes.lower() or "expedite" in plan.notes.lower()

    def test_academic_note(self):
        req = ContentRequirement(target_audience="academic")
        plan = self.planner.generate_plan(req)
        assert "academic" in plan.notes.lower() or "reference" in plan.notes.lower()

    def test_plan_to_dict(self):
        req = self.planner.analyse_requirement("写一篇文章")
        plan = self.planner.generate_plan(req)
        d = plan.to_dict()
        assert "plan_id" in d
        assert "writing_outline" in d
        assert "image_plan" in d

    def test_end_to_end(self):
        result = self.planner.plan("写一篇关于水网智能化的技术文章发公众号")
        assert "plan_id" in result
        assert "writing_outline" in result
        assert len(result["writing_outline"]) > 0
