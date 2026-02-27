"""Skill: Four-Prediction Loop — complete 四预闭环.
技能：四预完整闭环 — 预报→预警→预演→预案 一键执行。

This is the top-level Skill for emergency command personnel (应急指挥人员).
It chains the four sub-skills in sequence, with conditional logic:
    1. Forecast (always)
    2. Warning (always, based on forecast)
    3. Rehearsal (if warning >= yellow)
    4. Plan (if rehearsal was triggered)
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult
from skills.forecast_skill import ForecastSkill
from skills.plan_skill import PlanSkill
from skills.rehearsal_skill import RehearsalSkill
from skills.warning_skill import WarningSkill


class FourPredictionLoopSkill(BaseSkill):
    """Four-Prediction Loop Skill — complete emergency decision pipeline.
    四预完整闭环 Skill — 完整应急决策管道。

    Steps:
        1. 预报 Forecast: Predict future water levels
        2. 预警 Warning: Generate graded alert
        3. 预演 Rehearsal: Multi-scheme simulation (if warning >= yellow)
        4. 预案 Plan: Emergency dispatch plan (if rehearsal triggered)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._forecast_skill = ForecastSkill()
        self._warning_skill = WarningSkill()
        self._rehearsal_skill = RehearsalSkill()
        self._plan_skill = PlanSkill()
        self._sub_skills = [
            self._forecast_skill, self._warning_skill,
            self._rehearsal_skill, self._plan_skill,
        ]

    def register_tool(self, name, tool_fn):
        """Register a tool for this skill and all sub-skills."""
        super().register_tool(name, tool_fn)
        for sub in self._sub_skills:
            sub.register_tool(name, tool_fn)

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        historical_data = params.get("historical_data", [])

        if not historical_data:
            return SkillResult(success=False, error="No historical_data provided for 四预 loop")

        # Step 1: 预报 Forecast
        forecast_result = await self._forecast_skill.run({
            "historical_data": historical_data,
            "horizon": params.get("horizon", 60),
            "model": params.get("model", "linear"),
        })

        if not forecast_result.success:
            return SkillResult(
                success=False,
                error=f"Forecast failed: {forecast_result.error}",
                steps_completed=["forecast_failed"],
            )
        steps.append("forecast")

        # Step 2: 预警 Warning
        warning_result = await self._warning_skill.run({
            "forecast": forecast_result.data.get("forecast"),
            "odd_config": params.get("odd_config"),
        })

        if not warning_result.success:
            return SkillResult(
                success=False,
                error=f"Warning failed: {warning_result.error}",
                steps_completed=steps + ["warning_failed"],
            )
        steps.append("warning")

        # Step 3: 预演 Rehearsal (conditional: only if warning >= yellow)
        rehearsal_result = None
        plan_result = None
        warning_level = warning_result.data.get("warning_level", "none")

        if warning_level in ("yellow", "orange", "red"):
            rehearsal_result = await self._rehearsal_skill.run({
                "schemes": params.get("schemes"),
                "duration": params.get("duration", 600),
            })
            steps.append("rehearsal")

            if rehearsal_result.success:
                # Step 4: 预案 Plan
                plan_result = await self._plan_skill.run({
                    "rehearsal": rehearsal_result.data,
                    "constraints": params.get("constraints", {}),
                })
                steps.append("plan")

        # Generate executive summary
        summary = self._generate_summary(
            forecast_result.data,
            warning_result.data,
            rehearsal_result.data if rehearsal_result and rehearsal_result.success else None,
            plan_result.data if plan_result and plan_result.success else None,
        )

        return SkillResult(
            success=True,
            data={
                "forecast": forecast_result.data,
                "warning": warning_result.data,
                "rehearsal": (
                    rehearsal_result.data
                    if rehearsal_result and rehearsal_result.success
                    else None
                ),
                "plan": plan_result.data if plan_result and plan_result.success else None,
                "summary": summary,
                "warning_level": warning_level,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _generate_summary(
        forecast: dict,
        warning: dict,
        rehearsal: dict | None,
        plan: dict | None,
    ) -> dict:
        """Generate executive summary for decision makers.
        为决策者生成执行摘要。
        """
        predictions = forecast.get("forecast", {}).get("predictions", [])
        return {
            "四预_status": {
                "预报": "completed",
                "预警": warning.get("warning_level", "unknown"),
                "预演": "completed" if rehearsal else "skipped (warning level insufficient)",
                "预案": "completed" if plan else "skipped",
            },
            "forecast_range": {
                "min": min(predictions) if predictions else None,
                "max": max(predictions) if predictions else None,
            },
            "warning_level": warning.get("warning_level", "none"),
            "recommended_action": warning.get("recommended_action", ""),
            "best_scheme": (
                rehearsal.get("ranking", [{}])[0].get("label", "N/A")
                if rehearsal and rehearsal.get("ranking") else "N/A"
            ),
            "plan_approved": (
                plan.get("safety_check", {}).get("zone") != "mrc"
                if plan else None
            ),
        }
