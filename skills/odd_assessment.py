"""Skill: ODD Safety Assessment — fixed workflow.
技能：ODD 安全评估 — 固定工作流。

Pipeline: ODD Check → Simulation Scan → Boundary Calibration → Report
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class ODDAssessmentSkill(BaseSkill):
    """ODD safety assessment Skill.
    ODD 安全评估 Skill。

    Steps:
        1. Check current state against ODD
        2. Scan boundary scenarios via simulation
        3. Generate MRC plan if violations found
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        current_state = params.get("current_state", {"water_level": 1.0})
        odd_config = params.get("odd_config")

        # Step 1: Check current ODD status
        odd_result = await self.call_tool("check_odd", {
            "current_state": current_state,
            "odd_config": odd_config,
        })
        steps.append("odd_check")

        # Step 2: Scan boundary scenarios
        scan_scenarios = params.get("scan_scenarios", [
            {"q_in_profile": [[0, 0.01], [300, 0.05]], "initial_h": 0.5, "duration": 600},
            {"q_in_profile": [[0, 0.04], [300, 0.04]], "initial_h": 1.5, "duration": 600},
            {"q_in_profile": [[0, 0.0], [300, 0.0]], "initial_h": 0.3, "duration": 600},
        ])

        scan_results = []
        for scenario in scan_scenarios:
            sim = await self.call_tool("simulate_tank", {
                "duration": scenario.get("duration", 600),
                "dt": scenario.get("dt", 1.0),
                "q_in_profile": scenario.get("q_in_profile"),
                "initial_h": scenario.get("initial_h", 0.5),
            })

            # Check each simulated state against ODD
            states = [
                {"water_level": h}
                for h in sim["water_level"]
            ]
            series_check = await self.call_tool("check_odd", {
                "current_state": states[0] if states else current_state,
                "odd_config": odd_config,
                "check_mode": "predictive",
                "forecast_series": states,
                "time_series": sim["time"],
            })

            scan_results.append({
                "scenario": scenario,
                "max_level": max(sim["water_level"]),
                "min_level": min(sim["water_level"]),
                "odd_assessment": series_check,
            })
        steps.append("boundary_scan")

        # Step 3: Generate MRC plan if current state has violations
        mrc_plan = None
        if odd_result.get("violations"):
            mrc_plan = await self.call_tool("get_mrc_plan", {
                "violations": odd_result["violations"],
                "current_state": current_state,
            })
            steps.append("mrc_plan_generation")

        return SkillResult(
            success=True,
            data={
                "current_odd_status": odd_result,
                "scan_results": scan_results,
                "mrc_plan": mrc_plan,
                "overall_assessment": self._summarize(odd_result, scan_results),
            },
            steps_completed=steps,
        )

    @staticmethod
    def _summarize(odd_result: dict, scan_results: list) -> dict:
        """Summarize assessment results. / 汇总评估结果。"""
        n_scenarios = len(scan_results)
        n_violations = sum(
            1 for s in scan_results
            if s["odd_assessment"].get("worst_zone") == "mrc"
        )
        return {
            "current_zone": odd_result.get("zone", "unknown"),
            "scenarios_tested": n_scenarios,
            "scenarios_with_violations": n_violations,
            "safety_rating": "safe" if n_violations == 0 else "at_risk",
        }
