"""Skill: Reuse Scheduling — optimize water reuse and recycling.
技能：回用调度 — 优化水回用与循环利用。

Matches water sources to demands based on quality requirements,
optimizes reuse scheduling, and evaluates economic/environmental benefits.
基于水质要求匹配水源与需求，优化回用调度，评估经济与环境效益。
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class ReuseSchedulingSkill(BaseSkill):
    """Reuse Scheduling Skill — optimize water reuse paths and schedules.
    回用调度 Skill — 优化水回用路径与调度计划。

    Steps:
        1. Water quality matching (source -> demand)
        2. Scheduling optimization
        3. Benefit evaluation
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        source_quality = params.get("source_quality", {})
        target_requirements = params.get("target_requirements", [])
        sources = params.get("sources", [])
        demands = params.get("demands", [])
        current_reuse_rate = params.get("current_reuse_rate", 0.0)

        if not source_quality or not target_requirements:
            return SkillResult(
                success=False,
                error="source_quality and target_requirements are required",
            )

        # Step 1: Water quality matching
        match_result = await self.call_tool("match_reuse_path", {
            "source_quality": source_quality,
            "target_requirements": target_requirements,
        })
        if isinstance(match_result, dict) and "error" in match_result:
            return SkillResult(
                success=False,
                error=f"Quality matching failed: {match_result['error']}",
            )
        steps.append("quality_matching")

        # Step 2: Scheduling optimization
        if not sources:
            sources = match_result.get("matched_sources", [])
        if not demands:
            demands = match_result.get("matched_demands", [])

        schedule_result = await self.call_tool("optimize_reuse_schedule", {
            "sources": sources,
            "demands": demands,
            "match_paths": match_result.get("paths", []),
        })
        if isinstance(schedule_result, dict) and "error" in schedule_result:
            return SkillResult(
                success=False,
                error=f"Scheduling optimization failed: {schedule_result['error']}",
            )
        steps.append("schedule_optimization")

        # Step 3: Benefit evaluation
        benefit_result = await self.call_tool("evaluate_reuse_benefit", {
            "schedule": schedule_result,
            "current_reuse_rate": current_reuse_rate,
        })
        if isinstance(benefit_result, dict) and "error" in benefit_result:
            return SkillResult(
                success=False,
                error=f"Benefit evaluation failed: {benefit_result['error']}",
            )
        steps.append("benefit_evaluation")

        # Compute improvement summary
        improvement = self._compute_improvement(benefit_result, current_reuse_rate)

        return SkillResult(
            success=True,
            data={
                "matching": match_result,
                "schedule": schedule_result,
                "benefit": benefit_result,
                "improvement": improvement,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _compute_improvement(benefit: dict, current_rate: float) -> dict:
        """Compute improvement metrics from benefit evaluation.
        从效益评估中计算改进指标。
        """
        new_rate = benefit.get("new_reuse_rate", current_rate)
        rate_change = new_rate - current_rate
        water_saved = benefit.get("water_saved_m3_per_day", 0.0)
        cost_saved = benefit.get("cost_saved_per_day", 0.0)

        return {
            "reuse_rate_before": current_rate,
            "reuse_rate_after": new_rate,
            "reuse_rate_improvement": rate_change,
            "water_saved_m3_per_day": water_saved,
            "cost_saved_per_day": cost_saved,
            "summary": (
                f"Reuse rate improved from {current_rate:.1%} to {new_rate:.1%} "
                f"(+{rate_change:.1%}), saving {water_saved:.1f} m3/d. "
                f"回用率从 {current_rate:.1%} 提升至 {new_rate:.1%}，"
                f"日节水 {water_saved:.1f} m3。"
            ),
        }
