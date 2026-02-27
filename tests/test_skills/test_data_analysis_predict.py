"""Integration tests for DataAnalysisPredictSkill."""

import pytest

from skills.data_analysis_predict import DataAnalysisPredictSkill


class TestDataAnalysisPredictSkill:
    @pytest.mark.asyncio
    async def test_basic_workflow(self, sample_noisy_series):
        skill = DataAnalysisPredictSkill()
        result = await skill.run({
            "raw_data": sample_noisy_series,
            "horizon": 10,
            "model": "linear",
        })
        assert result.success
        assert "data_cleaning" in result.steps_completed
        assert "prediction" in result.steps_completed
        assert len(result.data["predictions"]) == 10
        assert len(result.data["cleaned_data"]) == len(sample_noisy_series)

    @pytest.mark.asyncio
    async def test_empty_data(self):
        skill = DataAnalysisPredictSkill()
        result = await skill.run({"raw_data": []})
        assert not result.success
        assert "No raw_data" in result.error
