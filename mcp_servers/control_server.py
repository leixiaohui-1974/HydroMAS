"""MCP Server: Control tools for water level regulation.
MCP 服务器：水位控制工具。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Control")


@mcp.tool()
def run_controller(
    setpoint: float,
    current_state: dict | None = None,
    controller_type: str = "PID",
    params: dict | None = None,
    simulation_config: dict | None = None,
) -> dict:
    """Run a controller for water level regulation.
    运行水位调节控制器。

    Can run in two modes:
    1. Single step: given current_state, returns control action
    2. Full simulation: runs closed-loop control for duration

    Args:
        setpoint: Target water level (m) / 目标水位
        current_state: Current state {h, q_out} for single-step mode / 当前状态
        controller_type: "PID" or "MPC" / 控制器类型
        params: Controller parameters / 控制器参数
        simulation_config: {duration, dt, initial_h, tank_params} for sim mode / 仿真配置

    Returns:
        Dict with control output or full simulation results.
    """
    import math
    if not math.isfinite(setpoint):
        raise ValueError(f"setpoint must be a finite number, got {setpoint}")
    if controller_type.upper() not in ("PID", "MPC"):
        raise ValueError(f"Unknown controller_type: {controller_type}. Use 'PID' or 'MPC'.")

    if simulation_config:
        # Full closed-loop simulation mode
        sim = simulation_config
        if controller_type.upper() == "PID":
            from core.control.pid_controller import run_pid_control
            return run_pid_control(
                setpoint=setpoint,
                initial_h=sim.get("initial_h", 0.5),
                duration=sim.get("duration", 300),
                dt=sim.get("dt", 1.0),
                pid_params=params,
                tank_params=sim.get("tank_params"),
            )
        elif controller_type.upper() == "MPC":
            from core.control.mpc_controller import run_mpc_control
            return run_mpc_control(
                setpoint=setpoint,
                initial_h=sim.get("initial_h", 0.5),
                duration=sim.get("duration", 300),
                dt=sim.get("dt", 1.0),
                mpc_params=params,
                tank_params=sim.get("tank_params"),
            )

    # Single-step mode
    state = current_state or {"h": 0.5}
    if "h" not in state:
        raise ValueError("current_state must contain key 'h' (water level)")
    if controller_type.upper() == "PID":
        from core.control.pid_controller import PIDController, PIDParams
        _pid_keys = {"kp", "ki", "kd", "output_min", "output_max", "anti_windup"}
        filtered = {k: v for k, v in (params or {}).items() if k in _pid_keys}
        pid = PIDController(PIDParams(**filtered))
        u = pid.compute(setpoint, state["h"])
        return {"control_output": u, "error": setpoint - state["h"]}
    elif controller_type.upper() == "MPC":
        from core.control.mpc_controller import MPCController
        _mpc_keys = {"horizon", "q_weight", "r_weight", "u_min", "u_max", "h_min", "h_max", "tank_area", "dt"}
        filtered = {k: v for k, v in (params or {}).items() if k in _mpc_keys}
        mpc = MPCController(**filtered)
        u = mpc.compute(state["h"], setpoint, state.get("q_out", 0.005))
        return {"control_output": u, "error": setpoint - state["h"]}

    # Unreachable: validation at top of function covers all invalid cases.
    # Retained as defensive guard.
    raise ValueError(f"Unknown controller_type: {controller_type}. Use 'PID' or 'MPC'.")


if __name__ == "__main__":
    mcp.run()
