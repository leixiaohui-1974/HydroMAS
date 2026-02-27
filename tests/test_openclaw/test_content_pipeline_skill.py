"""Tests for ContentPipelineSkill."""

from __future__ import annotations

import asyncio

from openclaw.skills.content_pipeline_skill import ContentPipelineSkill


class TestContentPipelineSkill:
    def setup_method(self):
        self.skill = ContentPipelineSkill()

    def test_metadata(self):
        assert self.skill.metadata.name == "content_pipeline"
        assert len(self.skill.metadata.trigger_phrases) > 0

    def test_execute_missing_requirement(self):
        result = asyncio.get_event_loop().run_until_complete(
            self.skill.execute({})
        )
        assert not result.success
        assert "requirement" in result.error.lower()

    def test_execute_basic(self):
        result = asyncio.get_event_loop().run_until_complete(
            self.skill.execute({
                "requirement": "写一篇关于水网AI的文章",
            })
        )
        assert result.success
        assert "pipeline_id" in result.data
        assert result.execution_time > 0
        assert len(result.steps_completed) > 0

    def test_execute_with_content(self):
        result = asyncio.get_event_loop().run_until_complete(
            self.skill.execute({
                "requirement": "发布文章",
                "content": "# Test Article\\n\\n## Introduction\\n\\nThis is test content.",
            })
        )
        assert result.success

    def test_execute_with_channels(self):
        result = asyncio.get_event_loop().run_until_complete(
            self.skill.execute({
                "requirement": "写文章发公众号",
                "channels": ["feishu", "wechat"],
            })
        )
        assert result.success
