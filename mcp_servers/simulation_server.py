"""MCP Server: Simulation tools for tank modeling.
MCP 服务器：水箱仿真工具。

Exposes simulate_tank and simulate_batch as MCP tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Simulation")


@mcp.tool()
def simulate_tank(
    duration: float,
    dt: float = 1.0,
    q_in_profile: list[list[float]] | None = None,
    initial_h: float = 0.5,
    tank_params: dict | None = None,
    solver: str = "rk4",
) -> dict:
    """Run a single-tank hydraulic simulation.
    运行单水箱水力仿真。

    Args:
        duration: Simulation duration in seconds / 仿真时长（秒）
        dt: Time step in seconds / 时间步长（秒）
        q_in_profile: Inflow profile as [[t, Q_in], ...] / 入流时序
        initial_h: Initial water level in meters / 初始水位（米）
        tank_params: Tank parameters {area, cd, outlet_area} / 水箱参数
        solver: Solver type ("euler" or "rk4") / 求解器类型

    Returns:
        Dict with time, water_level, outflow, inflow arrays and metadata.
    """
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")
    if dt <= 0:
        raise ValueError(f"dt must be positive, got {dt}")

    from core.simulation.simulator import run_simulation

    profile = None
    if q_in_profile:
        for i, row in enumerate(q_in_profile):
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                raise ValueError(f"q_in_profile row {i} must have [time, value], got {row!r}")
        profile = [(row[0], row[1]) for row in q_in_profile]

    return run_simulation(
        duration=duration,
        dt=dt,
        q_in_profile=profile,
        initial_h=initial_h,
        tank_params=tank_params,
        solver=solver,
    )


@mcp.tool()
def simulate_batch(
    schemes: list[dict],
    parallel: bool = True,
    duration: float = 3600,
) -> list[dict]:
    """Run multiple simulation schemes (optionally in parallel via Ray).
    运行多个仿真方案（可选 Ray 并行）。

    Args:
        schemes: List of simulation parameter dicts / 仿真参数列表
        parallel: Use Ray for parallel execution / 是否使用 Ray 并行
        duration: Default duration if not specified in schemes / 默认仿真时长

    Returns:
        List of simulation results.
    """
    if not schemes:
        raise ValueError("schemes list cannot be empty")

    from compute.distributed_sim import parameter_sweep

    param_grid = []
    for scheme in schemes:
        params = dict(scheme)
        params.setdefault("duration", duration)
        # Convert q_in_profile format
        if "q_in_profile" in params and params["q_in_profile"]:
            for i, row in enumerate(params["q_in_profile"]):
                if not isinstance(row, (list, tuple)) or len(row) < 2:
                    raise ValueError(f"scheme q_in_profile row {i} must have [time, value], got {row!r}")
            params["q_in_profile"] = [
                (row[0], row[1]) for row in params["q_in_profile"]
            ]
        param_grid.append(params)

    return parameter_sweep(param_grid, use_ray=parallel)


@mcp.tool()
def simulate_network(inp_file: str, duration: float, dt: float = 300.0,
                     scenarios: list[dict] | None = None) -> dict:
    """Run network hydraulic simulation via WNTR. / WNTR管网水力仿真。"""
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")
    from core.simulation.network_model import run_hydraulic_sim
    result = run_hydraulic_sim(inp_file=inp_file, duration=duration, dt=dt)
    if scenarios:
        result["scenarios_applied"] = len(scenarios)
    return result


if __name__ == "__main__":
    mcp.run()
