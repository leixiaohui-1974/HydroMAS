"""Skill: Optimization Design — fixed workflow.
技能：优化设计 — 固定工作流。

Pipeline: Design optimization → Simulation verification → Sensitivity analysis → Evaluation
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class OptimizationDesignSkill(BaseSkill):
    """Optimization design Skill.
    优化设计 Skill。

    Steps:
        1. Optimize tank design parameters
        2. Verify with simulation
        3. Sensitivity analysis
        4. Performance evaluation
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        requirements = params.get("requirements", {})
        design_space = params.get("design_space", {})
        objective = params.get("objective", "minimize_cost")

        # Step 1: Optimize design
        design_result = await self.call_tool("optimize_design", {
            "requirements": requirements,
            "design_space": design_space,
            "objective": objective,
        })
        steps.append("design_optimization")

        # Step 2: Verify optimal design with simulation
        optimal_area = design_result.get("optimal_area", 1.0)
        sim_result = await self.call_tool("simulate_tank", {
            "duration": 600,
            "dt": 1.0,
            "initial_h": design_result.get("optimal_height", 1.0) / 2,
            "tank_params": {"area": optimal_area},
        })
        steps.append("simulation_verification")

        # Step 3: Sensitivity analysis
        base_params = {"area": optimal_area, "cd": 0.6, "outlet_area": 0.01}
        sens_result = await self.call_tool("run_sensitivity", {
            "base_params": base_params,
            "param_ranges": {
                "area": [optimal_area * 0.5, optimal_area * 1.5],
                "cd": [0.3, 0.9],
                "outlet_area": [0.005, 0.02],
            },
            "method": "OAT",
            "n_levels": 8,
        })
        steps.append("sensitivity_analysis")

        return SkillResult(
            success=True,
            data={
                "optimal_design": design_result,
                "verification_simulation": sim_result,
                "sensitivity_analysis": sens_result,
            },
            steps_completed=steps,
        )
