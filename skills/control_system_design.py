"""Skill: Control System Design — fixed workflow.
技能：控制系统设计 — 固定工作流。

Pipeline: Simulate → Identify → Control → Evaluate
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class ControlSystemDesignSkill(BaseSkill):
    """Control system design Skill — immutable workflow.
    控制系统设计 Skill — 不可修改的工作流。

    Steps:
        1. Open-loop simulation to get plant response
        2. System identification from simulation data
        3. Controller design + closed-loop simulation
        4. Performance evaluation
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        controller_type = params.get("controller_type", "PID")
        setpoint = params.get("setpoint", 1.0)
        initial_h = params.get("initial_h", 0.5)
        duration = params.get("duration", 300)
        dt = params.get("dt", 1.0)

        # Step 1: Open-loop simulation — get plant response
        q_in_step = [[0, 0.01], [duration / 3, 0.03], [2 * duration / 3, 0.01]]
        sim_result = await self.call_tool("simulate_tank", {
            "duration": duration,
            "dt": dt,
            "q_in_profile": q_in_step,
            "initial_h": initial_h,
        })
        steps.append("open_loop_simulation")

        # Step 2: System identification from simulation data
        id_result = await self.call_tool("identify_parameters", {
            "observed_h": sim_result["water_level"],
            "observed_q_out": sim_result["outflow"],
            "model_type": "nonlinear",
        })
        steps.append("system_identification")

        # Step 3: Closed-loop control simulation
        ctrl_result = await self.call_tool("run_controller", {
            "setpoint": setpoint,
            "controller_type": controller_type,
            "simulation_config": {
                "duration": duration,
                "dt": dt,
                "initial_h": initial_h,
            },
        })
        steps.append("closed_loop_control")

        # Step 4: Performance evaluation
        n = min(len(ctrl_result["water_level"]), len(ctrl_result["water_level"]))
        reference = [setpoint] * n
        eval_result = await self.call_tool("evaluate_performance", {
            "observed": reference,
            "predicted": ctrl_result["water_level"][:n],
            "metrics": ["RMSE", "MAE", "settling_time", "overshoot", "steady_state_error"],
            "time_series": ctrl_result["time"][:n],
            "setpoint": setpoint,
        })
        steps.append("performance_evaluation")

        return SkillResult(
            success=True,
            data={
                "open_loop_simulation": sim_result,
                "identification": id_result,
                "controller_type": controller_type,
                "control_simulation": ctrl_result,
                "performance_metrics": eval_result,
            },
            steps_completed=steps,
        )
