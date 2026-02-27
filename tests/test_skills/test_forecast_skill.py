"""Integration tests for ForecastSkill (四预: 预报)."""

import pytest

from skills.forecast_skill import ForecastSkill


class TestForecastSkill:
    @pytest.mark.asyncio
    async def test_basic_forecast(self, sample_water_level_series):
        skill = ForecastSkill()
        result = await skill.run({
            "historical_data": sample_water_level_series,
            "horizon": 20,
            "model": "linear",
        })
        assert result.success
        assert "data_cleaning" in result.steps_completed
        assert "prediction" in result.steps_completed
        assert len(result.data["forecast"]["predictions"]) == 20
        assert result.data["confidence_level"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_polynomial_model(self, sample_water_level_series):
        skill = ForecastSkill()
        result = await skill.run({
            "historical_data": sample_water_level_series,
            "horizon": 10,
            "model": "polynomial",
        })
        assert result.success
        assert result.data["forecast"]["model"] == "polynomial"

    @pytest.mark.asyncio
    async def test_empty_data(self):
        skill = ForecastSkill()
        result = await skill.run({"historical_data": []})
        assert not result.success
