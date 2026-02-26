"""Integration tests for RehearsalSkill (四预: 预演)."""

import pytest
from skills.rehearsal_skill import RehearsalSkill


class TestRehearsalSkill:
    @pytest.mark.asyncio
    async def test_default_schemes(self):
        """Test rehearsal with default 3 schemes."""
        skill = RehearsalSkill()
        result = await skill.run({"duration": 100})
        assert result.success
        assert "batch_simulation" in result.steps_completed
        assert "scheme_evaluation" in result.steps_completed
        assert "ranking" in result.steps_completed
        assert len(result.data["ranking"]) == 3
        # First ranked should have rank=1
        assert result.data["ranking"][0]["rank"] == 1
        # Scores between 0 and 1
        for r in result.data["ranking"]:
            assert 0 <= r["total_score"] <= 1

    @pytest.mark.asyncio
    async def test_custom_schemes(self):
        """Test rehearsal with custom schemes."""
        schemes = [
            {"q_in_profile": [[0, 0.02]], "initial_h": 0.5, "label": "A"},
            {"q_in_profile": [[0, 0.03]], "initial_h": 0.5, "label": "B"},
        ]
        skill = RehearsalSkill()
        result = await skill.run({"schemes": schemes, "duration": 50})
        assert result.success
        assert len(result.data["sim_results"]) == 2
        assert len(result.data["ranking"]) == 2

    @pytest.mark.asyncio
    async def test_custom_weights(self):
        """Test with custom ranking weights."""
        skill = RehearsalSkill()
        result = await skill.run({
            "duration": 50,
            "weights": {"safety": 0.8, "efficiency": 0.1, "cost": 0.1},
        })
        assert result.success
        assert result.data["weights"]["safety"] == 0.8
