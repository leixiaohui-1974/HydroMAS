"""Skill: Forecast — predict future water levels (四预第一环: 预报).
技能：预报 — 基于历史数据预测未来水位。

Part of the Four-Prediction (四预) system:
    预报(Forecast) → 预警(Warning) → 预演(Rehearsal) → 预案(Plan)

MVP: Linear/polynomial model on historical data.
Extension: LSTM + meteorological API integration.
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class ForecastSkill(BaseSkill):
    """Forecast Skill — predict future water levels from historical data.
    预报 Skill — 从历史数据预测未来水位。

    Steps:
        1. Data cleaning (outlier removal + interpolation)
        2. Time series prediction
        3. Backtest accuracy evaluation
        4. Confidence level classification
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        historical_data = params.get("historical_data", [])
        horizon = params.get("horizon", 60)
        model = params.get("model", "linear")
        methods = params.get("cleaning_methods", ["outlier_3sigma", "interpolate_linear"])

        if not historical_data:
            return SkillResult(success=False, error="No historical_data provided")

        # Step 1: Data cleaning
        clean_result = await self.call_tool("clean_timeseries", {
            "raw_data": historical_data,
            "methods": methods,
        })
        if isinstance(clean_result, dict) and "error" in clean_result:
            return SkillResult(success=False, error=f"Data cleaning failed: {clean_result['error']}")
        cleaned = clean_result.get("data", historical_data)
        if not cleaned:
            return SkillResult(success=False, error="Data cleaning produced empty result")
        steps.append("data_cleaning")

        # Step 2: Prediction
        forecast = await self.call_tool("predict_future", {
            "historical_data": cleaned,
            "horizon": horizon,
            "model": model,
        })
        if isinstance(forecast, dict) and "error" in forecast:
            return SkillResult(success=False, error=f"Prediction failed: {forecast['error']}")
        steps.append("prediction")

        # Step 3: Backtest accuracy evaluation
        accuracy = {}
        if "backtest_fitted" in forecast:
            n = len(forecast["backtest_fitted"])
            accuracy = await self.call_tool("evaluate_performance", {
                "observed": cleaned[-n:],
                "predicted": forecast["backtest_fitted"],
                "metrics": ["RMSE", "NSE", "MAE"],
            })
            steps.append("accuracy_evaluation")

        # Step 4: Confidence classification
        confidence = self._compute_confidence(accuracy)

        return SkillResult(
            success=True,
            data={
                "forecast": {
                    "predictions": forecast.get("predictions", []),
                    "confidence_upper": forecast.get("confidence_upper", []),
                    "confidence_lower": forecast.get("confidence_lower", []),
                    "horizon": horizon,
                    "model": model,
                },
                "cleaned_data": cleaned,
                "accuracy": accuracy,
                "confidence_level": confidence,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _compute_confidence(accuracy: dict) -> str:
        """Classify forecast confidence based on accuracy metrics.
        基于精度指标分类预报置信度。

        Returns: "high", "medium", or "low"
        """
        nse = accuracy.get("NSE", 0)
        if nse > 0.8:
            return "high"
        elif nse > 0.5:
            return "medium"
        else:
            return "low"
