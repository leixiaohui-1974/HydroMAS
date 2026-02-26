"""Skill: Warning — graded alert generation (四预第二环: 预警).
技能：预警 — 分级告警生成。

Warning levels (aligned with Ministry of Water Resources standards):
    - None:   All parameters well within ODD
    - Blue:   Forecast values entering ODD extended zone
    - Yellow: Forecast values will exceed ODD within 2h
    - Orange: Forecast values will exceed ODD within 1h
    - Red:    Current values already outside ODD or MRC imminent

Part of: 预报(Forecast) → 预警(Warning) → 预演(Rehearsal) → 预案(Plan)
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


# Warning level thresholds (fraction of horizon until breach)
_WARNING_THRESHOLDS = {
    "red": 0.0,      # Already breached or imminent
    "orange": 0.15,   # Breach within ~15% of horizon
    "yellow": 0.30,   # Breach within ~30% of horizon
    "blue": 0.60,     # Breach within ~60% of horizon
}

_RECOMMENDED_ACTIONS = {
    "red": "Immediate MRC activation. Close inlet/open drain. Notify on-duty personnel. / 立即激活MRC。关闭进水/打开排水。通知值班人员。",
    "orange": "Prepare MRC procedures. Notify dispatcher. Increase monitoring frequency to 1min. / 准备MRC程序。通知调度员。监测频率提高至1分钟。",
    "yellow": "Alert dispatcher. Prepare contingency schemes. Monitoring frequency 5min. / 告警调度员。准备应急方案。监测频率5分钟。",
    "blue": "Monitor closely. Review forecast accuracy. Standard monitoring. / 密切关注。核查预报精度。标准监测频率。",
    "none": "Normal operation. / 正常运行。",
}


class WarningSkill(BaseSkill):
    """Warning Skill — generate graded alerts from forecast + ODD.
    预警 Skill — 从预报结果和 ODD 生成分级告警。

    Steps:
        1. Obtain forecast (from input or by calling forecast)
        2. Check forecast series against ODD boundaries (predictive mode)
        3. Classify warning level based on time-to-breach
        4. Generate warning message
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        odd_config = params.get("odd_config")

        # Step 1: Get forecast
        forecast_data = params.get("forecast")
        if not forecast_data:
            historical = params.get("historical_data", [])
            if not historical:
                return SkillResult(success=False, error="Need forecast or historical_data")
            # Run inline forecast
            clean_result = await self.call_tool("clean_timeseries", {
                "raw_data": historical,
                "methods": ["outlier_3sigma", "interpolate_linear"],
            })
            pred_result = await self.call_tool("predict_future", {
                "historical_data": clean_result["data"],
                "horizon": params.get("horizon", 60),
                "model": params.get("model", "linear"),
            })
            forecast_data = {
                "predictions": pred_result.get("predictions", []),
                "confidence_upper": pred_result.get("confidence_upper", []),
                "confidence_lower": pred_result.get("confidence_lower", []),
                "horizon": params.get("horizon", 60),
            }
            steps.append("inline_forecast")

        predictions = forecast_data.get("predictions", [])
        if not predictions:
            return SkillResult(success=False, error="No predictions available")

        # Step 2: Check predicted states against ODD (predictive mode)
        forecast_states = [{"water_level": h} for h in predictions]
        time_series = list(range(len(predictions)))

        odd_result = await self.call_tool("check_odd", {
            "current_state": forecast_states[0] if forecast_states else {"water_level": 1.0},
            "odd_config": odd_config,
            "check_mode": "predictive",
            "forecast_series": forecast_states,
            "time_series": [float(t) for t in time_series],
        })
        steps.append("odd_predictive_check")

        # Step 3: Classify warning level
        warning_level = self._classify_warning(odd_result, len(predictions))
        steps.append("warning_classification")

        # Step 4: Generate message
        message = self._format_warning_message(warning_level, odd_result, predictions)

        return SkillResult(
            success=True,
            data={
                "warning_level": warning_level,
                "violations": odd_result.get("step_results", []),
                "worst_zone": odd_result.get("worst_zone", "normal"),
                "time_to_breach": odd_result.get("time_to_breach"),
                "recommended_action": _RECOMMENDED_ACTIONS.get(warning_level, ""),
                "message": message,
                "forecast_used": forecast_data,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _classify_warning(odd_result: dict, horizon_length: int) -> str:
        """Classify warning level based on ODD check results.
        基于 ODD 检查结果分类预警等级。
        """
        worst_zone = odd_result.get("worst_zone", "normal")
        time_to_breach = odd_result.get("time_to_breach")

        if worst_zone == "normal":
            return "none"

        if time_to_breach is None:
            # Extended zone but no MRC breach
            return "blue"

        # Normalize time_to_breach against horizon
        breach_fraction = time_to_breach / max(horizon_length, 1)

        if breach_fraction <= _WARNING_THRESHOLDS["red"]:
            return "red"
        elif breach_fraction <= _WARNING_THRESHOLDS["orange"]:
            return "orange"
        elif breach_fraction <= _WARNING_THRESHOLDS["yellow"]:
            return "yellow"
        else:
            return "blue"

    @staticmethod
    def _format_warning_message(level: str, odd_result: dict, predictions: list) -> str:
        """Format a human-readable warning message.
        格式化人类可读的预警消息。
        """
        level_names = {
            "none": "正常 / Normal",
            "blue": "蓝色预警 / Blue Warning",
            "yellow": "黄色预警 / Yellow Warning",
            "orange": "橙色预警 / Orange Warning",
            "red": "红色预警 / Red Warning",
        }

        msg = f"【{level_names.get(level, level)}】"

        ttb = odd_result.get("time_to_breach")
        if ttb is not None:
            msg += f" ODD breach predicted at t={ttb:.0f}s."

        if predictions:
            msg += f" Predicted range: [{min(predictions):.3f}, {max(predictions):.3f}] m."

        return msg
