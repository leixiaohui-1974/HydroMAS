"""Tests for CollaborativeDevSkill."""

from __future__ import annotations

import asyncio

from skills.collaborative_dev import CollaborativeDevSkill


class TestCollaborativeDevSkill:
    """Test the collaborative development skill."""

    def setup_method(self):
        self.skill = CollaborativeDevSkill()

    def test_metadata(self):
        assert self.skill.metadata.name == "collaborative_dev"
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
                "requirement": "Add new water balance check",
                "modules": ["water_balance"],
            })
        )
        assert result.success
        assert "pipeline" in result.data
        assert len(result.steps_completed) > 0

    def test_execute_with_files(self):
        result = asyncio.get_event_loop().run_until_complete(
            self.skill.execute({
                "requirement": "New core module",
                "files": {
                    "core/new.py": (
                        '"""New module."""\n'
                        'def f():\n'
                        '    """Doc."""\n'
                        '    return 1\n'
                    ),
                },
                "modules": ["simulation"],
            })
        )
        assert result.success
        assert result.data.get("review") is not None

    def test_execute_with_scenario(self):
        result = asyncio.get_event_loop().run_until_complete(
            self.skill.execute({
                "requirement": "Evaporation research feature",
                "modules": ["evaporation"],
                "scenario": "research",
            })
        )
        assert result.success

    def test_execution_time_tracked(self):
        result = asyncio.get_event_loop().run_until_complete(
            self.skill.execute({
                "requirement": "Quick change",
            })
        )
        assert result.execution_time > 0
