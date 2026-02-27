"""Integration tests for ODDAssessmentSkill."""

import pytest

from skills.odd_assessment import ODDAssessmentSkill


class TestODDAssessmentSkill:
    @pytest.mark.asyncio
    async def test_safe_state(self):
        skill = ODDAssessmentSkill()
        result = await skill.run({
            "current_state": {"water_level": 1.0},
        })
        assert result.success
        assert "odd_check" in result.steps_completed
        assert "boundary_scan" in result.steps_completed
        assert result.data["current_odd_status"]["zone"] == "normal"

    @pytest.mark.asyncio
    async def test_mrc_state(self):
        skill = ODDAssessmentSkill()
        result = await skill.run({
            "current_state": {"water_level": 2.5},
        })
        assert result.success
        assert result.data["current_odd_status"]["zone"] == "mrc"
        assert result.data["mrc_plan"] is not None
        assert "mrc_plan_generation" in result.steps_completed
