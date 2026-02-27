"""Integration tests for FourPredictionLoopSkill (四预闭环)."""

import pytest

from skills.four_prediction_loop import FourPredictionLoopSkill


class TestFourPredictionLoopSkill:
    @pytest.mark.asyncio
    async def test_safe_scenario(self, sample_water_level_series):
        """Test 四预 loop with data that stays within ODD (low warning)."""
        skill = FourPredictionLoopSkill()
        result = await skill.run({
            "historical_data": sample_water_level_series,
            "horizon": 20,
        })
        assert result.success
        assert "forecast" in result.steps_completed
        assert "warning" in result.steps_completed
        # Summary should exist
        assert result.data["summary"] is not None
        assert "四预_status" in result.data["summary"]
        assert result.data["summary"]["四预_status"]["预报"] == "completed"

    @pytest.mark.asyncio
    async def test_dangerous_scenario(self):
        """Test 四预 with data trending toward ODD breach → should trigger rehearsal + plan."""
        # Generate data trending sharply upward to breach ODD
        data = [0.5 + 0.015 * i for i in range(100)]  # reaches ~2.0 at end
        skill = FourPredictionLoopSkill()
        result = await skill.run({
            "historical_data": data,
            "horizon": 30,
        })
        assert result.success
        # Should have at least forecast + warning
        assert "forecast" in result.steps_completed
        assert "warning" in result.steps_completed

    @pytest.mark.asyncio
    async def test_no_data_error(self):
        skill = FourPredictionLoopSkill()
        result = await skill.run({})
        assert not result.success
        assert "historical_data" in result.error

    @pytest.mark.asyncio
    async def test_summary_structure(self, sample_water_level_series):
        skill = FourPredictionLoopSkill()
        result = await skill.run({
            "historical_data": sample_water_level_series,
            "horizon": 10,
        })
        assert result.success
        summary = result.data["summary"]
        assert "warning_level" in summary
        assert "forecast_range" in summary
