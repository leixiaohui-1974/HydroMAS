"""Skill: Evaporation Optimization — minimize evaporative water losses.
技能：蒸发优化 — 最小化蒸发水损失。

Predicts evaporation from cooling towers, calcination processes, and red mud
storage, then generates optimization suggestions to reduce total evap loss.
预测冷却塔、焙烧工艺和赤泥堆场的蒸发量，并生成降低总蒸发损失的优化建议。
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class EvapOptimizationSkill(BaseSkill):
    """Evaporation Optimization Skill — predict and reduce evaporative losses.
    蒸发优化 Skill — 预测并降低蒸发损失。

    Steps:
        1. Predict cooling tower evaporation
        2. Predict calcination evaporation
        3. Predict red mud water loss
        4. Calculate total evaporation loss
        5. Generate optimization suggestions
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        tower_params = params.get("tower_params", {})
        weather = params.get("weather", {})
        calc_params = params.get("calc_params", {})
        mud_params = params.get("mud_params", {})

        if not tower_params and not calc_params and not mud_params:
            return SkillResult(
                success=False,
                error="At least one of tower_params, calc_params, or mud_params is required",
            )

        # Step 1: Predict cooling tower evaporation
        tower_result = {}
        if tower_params:
            tower_result = await self.call_tool("predict_evaporation", {
                "tower_params": tower_params,
                "weather": weather,
            })
            if isinstance(tower_result, dict) and "error" in tower_result:
                return SkillResult(
                    success=False,
                    error=f"Tower evaporation prediction failed: {tower_result['error']}",
                )
            steps.append("tower_evaporation")

        # Step 2: Predict calcination evaporation
        calc_result = {}
        if calc_params:
            calc_result = await self.call_tool("predict_calcination_evap", {
                "calc_params": calc_params,
            })
            if isinstance(calc_result, dict) and "error" in calc_result:
                return SkillResult(
                    success=False,
                    error=f"Calcination evaporation prediction failed: {calc_result['error']}",
                )
            steps.append("calcination_evaporation")

        # Step 3: Predict red mud water loss
        mud_result = {}
        if mud_params:
            mud_result = await self.call_tool("predict_red_mud_water", {
                "mud_params": mud_params,
            })
            if isinstance(mud_result, dict) and "error" in mud_result:
                return SkillResult(
                    success=False,
                    error=f"Red mud water prediction failed: {mud_result['error']}",
                )
            steps.append("red_mud_water")

        # Step 4: Calculate total evaporation loss
        total_result = await self.call_tool("predict_total_evap_loss", {
            "tower_params": tower_params,
            "weather": weather,
            "calc_params": calc_params,
            "mud_params": mud_params,
        })
        if isinstance(total_result, dict) and "error" in total_result:
            return SkillResult(
                success=False,
                error=f"Total evap loss prediction failed: {total_result['error']}",
            )
        steps.append("total_evap_loss")

        # Step 5: Generate optimization suggestions
        suggestions = self._generate_suggestions(
            tower_result, calc_result, mud_result, total_result, weather,
        )
        steps.append("optimization_suggestions")

        return SkillResult(
            success=True,
            data={
                "tower_evaporation": tower_result,
                "calcination_evaporation": calc_result,
                "red_mud_water": mud_result,
                "total_evap_loss": total_result,
                "suggestions": suggestions,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _generate_suggestions(
        tower: dict,
        calc: dict,
        mud: dict,
        total: dict,
        weather: dict,
    ) -> list[dict]:
        """Generate optimization suggestions based on evaporation predictions.
        基于蒸发预测生成优化建议。
        """
        suggestions = []
        total_loss = total.get("total_evap_loss", 0.0)

        # Tower optimization
        tower_loss = tower.get("evap_rate", 0.0)
        if total_loss > 0 and tower_loss / max(total_loss, 1e-9) > 0.5:
            suggestions.append({
                "target": "cooling_tower",
                "priority": "high",
                "action": (
                    "Cooling tower accounts for >50% of total evaporation. "
                    "Consider reducing circulation rate or adjusting fan speed. "
                    "冷却塔蒸发占比超过50%，建议降低循环量或调整风机转速。"
                ),
            })

        # Weather-based suggestion
        temp = weather.get("temperature", 25.0)
        humidity = weather.get("humidity", 0.5)
        if temp > 35 and humidity < 0.3:
            suggestions.append({
                "target": "scheduling",
                "priority": "high",
                "action": (
                    "High temperature and low humidity detected. "
                    "Shift water-intensive operations to cooler hours. "
                    "高温低湿环境，建议将用水密集操作调整至低温时段。"
                ),
            })

        # Red mud suggestion
        mud_loss = mud.get("water_loss", 0.0)
        if mud_loss > 0:
            suggestions.append({
                "target": "red_mud",
                "priority": "medium",
                "action": (
                    "Consider covering red mud storage areas to reduce evaporation. "
                    "建议覆盖赤泥堆场以减少蒸发损失。"
                ),
            })

        # General suggestion if total loss is high
        if total_loss > 1000:
            suggestions.append({
                "target": "general",
                "priority": "medium",
                "action": (
                    "Total evaporation loss exceeds 1000 m3/d. "
                    "Review all evaporation sources for reduction opportunities. "
                    "总蒸发损失超过1000 m3/d，建议全面审查各蒸发源的减量机会。"
                ),
            })

        if not suggestions:
            suggestions.append({
                "target": "general",
                "priority": "low",
                "action": (
                    "Evaporation levels are within normal range. "
                    "Continue monitoring. 蒸发水平在正常范围内，继续监测。"
                ),
            })

        return suggestions
