"""Skill: Data Analysis & Prediction — fixed workflow.
技能：数据分析预测 — 固定工作流。

Pipeline: Clean → Predict → Evaluate
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class DataAnalysisPredictSkill(BaseSkill):
    """Data analysis and prediction Skill.
    数据分析预测 Skill。

    Steps:
        1. Data cleaning (outlier detection + interpolation)
        2. Prediction (linear/polynomial/LSTM)
        3. Accuracy evaluation (backtest)
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        raw_data = params.get("raw_data", [])
        horizon = params.get("horizon", 60)
        model = params.get("model", "linear")
        methods = params.get("cleaning_methods", ["outlier_3sigma", "interpolate_linear"])

        if not raw_data:
            return SkillResult(success=False, error="No raw_data provided")

        # Step 1: Data cleaning
        clean_result = await self.call_tool("clean_timeseries", {
            "raw_data": raw_data,
            "methods": methods,
        })
        if isinstance(clean_result, dict) and "error" in clean_result:
            return SkillResult(
                success=False,
                error=f"Data cleaning failed: {clean_result['error']}",
            )
        cleaned_data = clean_result.get("data", raw_data)
        steps.append("data_cleaning")

        # Step 2: Prediction
        predict_result = await self.call_tool("predict_future", {
            "historical_data": cleaned_data,
            "horizon": horizon,
            "model": model,
        })
        steps.append("prediction")

        # Step 3: Evaluate backtest accuracy
        if "backtest_fitted" in predict_result:
            n = min(len(predict_result["backtest_fitted"]), len(cleaned_data))
            eval_result = await self.call_tool("evaluate_performance", {
                "observed": cleaned_data[-n:] if n > 0 else cleaned_data,
                "predicted": predict_result["backtest_fitted"],
                "metrics": ["RMSE", "NSE", "MAE"],
            })
            steps.append("accuracy_evaluation")
        else:
            eval_result = {}

        return SkillResult(
            success=True,
            data={
                "cleaned_data": cleaned_data,
                "cleaning_steps": clean_result.get("steps", []),
                "predictions": predict_result.get("predictions", []),
                "confidence_upper": predict_result.get("confidence_upper", []),
                "confidence_lower": predict_result.get("confidence_lower", []),
                "accuracy": eval_result,
                "model": model,
                "horizon": horizon,
            },
            steps_completed=steps,
        )
