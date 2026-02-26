"""Integration tests for WarningSkill (四预: 预警)."""

import pytest
from skills.warning_skill import WarningSkill


class TestWarningSkill:
    @pytest.mark.asyncio
    async def test_no_warning_safe_forecast(self):
        """Forecast within ODD should produce no warning."""
        skill = WarningSkill()
        result = await skill.run({
            "forecast": {
                "predictions": [1.0, 1.01, 1.02, 1.03],
                "horizon": 4,
            },
        })
        assert result.success
        assert result.data["warning_level"] == "none"

    @pytest.mark.asyncio
    async def test_warning_breach_forecast(self):
        """Forecast that breaches ODD should produce warning."""
        skill = WarningSkill()
        # Predictions that exceed ODD max (1.8m) quickly
        result = await skill.run({
            "forecast": {
                "predictions": [1.5, 1.7, 1.9, 2.0, 2.2],
                "horizon": 5,
            },
        })
        assert result.success
        assert result.data["warning_level"] in ("blue", "yellow", "orange", "red")
        assert result.data["worst_zone"] == "mrc"

    @pytest.mark.asyncio
    async def test_warning_from_historical_data(self, sample_water_level_series):
        """Test inline forecast from historical data."""
        skill = WarningSkill()
        result = await skill.run({
            "historical_data": sample_water_level_series,
            "horizon": 20,
        })
        assert result.success
        assert "inline_forecast" in result.steps_completed
        assert result.data["warning_level"] in ("none", "blue", "yellow", "orange", "red")

    @pytest.mark.asyncio
    async def test_no_data_error(self):
        skill = WarningSkill()
        result = await skill.run({})
        assert not result.success
