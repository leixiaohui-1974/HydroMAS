"""Skill: Global Dispatch — plant-wide water intake and dispatch optimization.
技能：全局调度 — 全厂取水与调度优化。

Combines demand prediction, evaporation forecasting, global optimization,
and ODD safety checks for optimal water dispatch decisions.
结合需求预测、蒸发预报、全局优化和ODD安全校验，实现最优取水调度决策。
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class GlobalDispatchSkill(BaseSkill):
    """Global Dispatch Skill — optimize plant-wide water intake and distribution.
    全局调度 Skill — 优化全厂取水与配水。

    Steps:
        1. Demand prediction
        2. Evaporation hybrid prediction
        3. Global dispatch optimization
        4. ODD safety check
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        historical_demand = params.get("historical_demand", [])
        weather_forecast = params.get("weather_forecast", [])
        supply_config = params.get("supply_config", {})
        current_state = params.get("current_state", {})

        if not historical_demand:
            return SkillResult(success=False, error="historical_demand is required")

        # Step 1: Demand prediction
        demand_result = await self.call_tool("predict_demand", {
            "historical_demand": historical_demand,
        })
        if isinstance(demand_result, dict) and "error" in demand_result:
            return SkillResult(
                success=False,
                error=f"Demand prediction failed: {demand_result['error']}",
            )
        steps.append("demand_prediction")

        # Step 2: Evaporation hybrid prediction
        evap_result = {}
        if weather_forecast:
            evap_result = await self.call_tool("predict_evaporation_hybrid", {
                "weather_forecast": weather_forecast,
            })
            if isinstance(evap_result, dict) and "error" in evap_result:
                return SkillResult(
                    success=False,
                    error=f"Evaporation prediction failed: {evap_result['error']}",
                )
            steps.append("evaporation_prediction")

        # Step 3: Global dispatch optimization
        dispatch_result = await self.call_tool("optimize_global_dispatch", {
            "demand_forecast": demand_result.get("predictions", []),
            "evap_forecast": evap_result.get("predictions", []),
            "supply_config": supply_config,
            "current_state": current_state,
        })
        if isinstance(dispatch_result, dict) and "error" in dispatch_result:
            return SkillResult(
                success=False,
                error=f"Dispatch optimization failed: {dispatch_result['error']}",
            )
        steps.append("dispatch_optimization")

        # Step 4: ODD safety check
        odd_result = await self.call_tool("check_alumina_odd", {
            "dispatch_plan": dispatch_result,
            "current_state": current_state,
        })
        if isinstance(odd_result, dict) and "error" in odd_result:
            return SkillResult(
                success=False,
                error=f"ODD safety check failed: {odd_result['error']}",
            )
        steps.append("odd_safety_check")

        # Build dispatch summary
        summary = self._build_dispatch_summary(
            demand_result, evap_result, dispatch_result, odd_result,
        )

        return SkillResult(
            success=True,
            data={
                "demand_forecast": demand_result,
                "evaporation_forecast": evap_result,
                "dispatch_plan": dispatch_result,
                "odd_check": odd_result,
                "summary": summary,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _build_dispatch_summary(
        demand: dict,
        evap: dict,
        dispatch: dict,
        odd: dict,
    ) -> dict:
        """Build a summary of the dispatch optimization results.
        构建调度优化结果摘要。
        """
        total_demand = sum(demand.get("predictions", []))
        total_evap = sum(evap.get("predictions", []))
        total_supply = dispatch.get("total_supply", 0.0)
        odd_zone = odd.get("zone", "normal")
        is_safe = odd_zone in ("normal", "extended")

        return {
            "total_predicted_demand": total_demand,
            "total_predicted_evap": total_evap,
            "total_planned_supply": total_supply,
            "odd_zone": odd_zone,
            "is_safe": is_safe,
            "message": (
                f"Dispatch plan: supply {total_supply:.1f} m³ for "
                f"demand {total_demand:.1f} m³ + evap {total_evap:.1f} m³. "
                f"ODD zone: {odd_zone}. "
                f"调度方案：供水 {total_supply:.1f} m³，"
                f"需求 {total_demand:.1f} m³ + 蒸发 {total_evap:.1f} m³，"
                f"ODD区域：{odd_zone}。"
            ),
        }
