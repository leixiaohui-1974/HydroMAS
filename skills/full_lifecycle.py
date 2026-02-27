"""Skill: Full Lifecycle Loop — combines multiple sub-skills.
技能：全生命周期闭环 — 组合多个子技能。

Pipeline: Design → Simulation → Identification → Control → ODD → Evaluation
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class FullLifecycleSkill(BaseSkill):
    """Full lifecycle Skill — orchestrates the complete design-to-operation pipeline.
    全生命周期 Skill — 编排完整的设计到运行管道。

    Steps:
        1. Tank design optimization
        2. Open-loop simulation
        3. System identification
        4. Controller design and closed-loop simulation
        5. ODD safety assessment
        6. Overall performance evaluation
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        setpoint = params.get("setpoint", 1.0)
        initial_h = params.get("initial_h", 0.5)
        controller_type = params.get("controller_type", "PID")
        duration = params.get("duration", 300)

        # Step 1: Design optimization
        design_result = await self.call_tool("optimize_design", {
            "requirements": {"peak_demand": 0.02, "min_reserve_time": 300},
        })
        steps.append("design_optimization")

        # Step 2: Open-loop simulation with optimized parameters
        optimal_area = design_result.get("optimal_area", 1.0)
        tank_params = {"area": optimal_area}

        sim_result = await self.call_tool("simulate_tank", {
            "duration": duration,
            "dt": 1.0,
            "q_in_profile": [[0, 0.01], [100, 0.03], [200, 0.01]],
            "initial_h": initial_h,
            "tank_params": tank_params,
        })
        steps.append("open_loop_simulation")

        # Step 3: System identification
        id_result = await self.call_tool("identify_parameters", {
            "observed_h": sim_result["water_level"],
            "observed_q_out": sim_result["outflow"],
        })
        steps.append("system_identification")

        # Step 4: Controller design + closed-loop
        ctrl_result = await self.call_tool("run_controller", {
            "setpoint": setpoint,
            "controller_type": controller_type,
            "simulation_config": {
                "duration": duration,
                "dt": 1.0,
                "initial_h": initial_h,
                "tank_params": tank_params,
            },
        })
        steps.append("closed_loop_control")

        # Step 5: ODD safety assessment
        water_levels = ctrl_result.get("water_level") or [initial_h]
        control_outputs = ctrl_result.get("control_output") or [0.0]
        mid_idx = len(water_levels) // 2
        odd_result = await self.call_tool("check_odd", {
            "current_state": {
                "water_level": water_levels[mid_idx],
                "inflow_rate": control_outputs[min(mid_idx, len(control_outputs) - 1)],
            },
        })
        steps.append("odd_assessment")

        # Step 6: Performance evaluation
        n = len(ctrl_result["water_level"])
        reference = [setpoint] * n
        eval_result = await self.call_tool("evaluate_performance", {
            "observed": reference,
            "predicted": ctrl_result["water_level"],
            "metrics": ["RMSE", "MAE", "NSE", "settling_time", "overshoot"],
            "time_series": ctrl_result["time"],
            "setpoint": setpoint,
        })
        steps.append("performance_evaluation")

        return SkillResult(
            success=True,
            data={
                "design": design_result,
                "simulation": sim_result,
                "identification": id_result,
                "control": ctrl_result,
                "odd_assessment": odd_result,
                "evaluation": eval_result,
                "summary": {
                    "tank_area": optimal_area,
                    "controller": controller_type,
                    "setpoint": setpoint,
                    "odd_zone": odd_result.get("zone", "unknown"),
                },
            },
            steps_completed=steps,
        )
