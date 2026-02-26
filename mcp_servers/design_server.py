"""MCP Server: Design optimization tools.
MCP 服务器：优化设计工具。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Design")


@mcp.tool()
def optimize_design(
    requirements: dict | None = None,
    design_space: dict | None = None,
    objective: str = "minimize_cost",
) -> dict:
    """Optimize tank design parameters.
    优化水箱设计参数。

    Args:
        requirements: Design requirements {peak_demand, min_reserve_time, ...} / 设计需求
        design_space: Parameter ranges {max_area, max_height, ...} / 设计空间
        objective: Optimization objective / 优化目标

    Returns:
        Dict with optimal dimensions, cost, and capacity.
    """
    from core.design.sizing import optimize_tank_size
    req = requirements or {}
    space = design_space or {}
    return optimize_tank_size(
        peak_demand=req.get("peak_demand", 0.02),
        min_reserve_time=req.get("min_reserve_time", 300.0),
        max_area=space.get("max_area", 10.0),
        max_height=space.get("max_height", 3.0),
        cost_per_m2=space.get("cost_per_m2", 1000.0),
        cost_per_m_height=space.get("cost_per_m_height", 500.0),
    )


@mcp.tool()
def run_sensitivity(
    base_params: dict[str, float],
    param_ranges: dict[str, list[float]],
    method: str = "OAT",
    n_levels: int = 10,
) -> dict:
    """Run sensitivity analysis on tank parameters.
    运行水箱参数敏感性分析。

    Args:
        base_params: Baseline parameter values / 基准参数值
        param_ranges: {param_name: [min, max]} ranges / 参数范围
        method: "OAT" or "Morris" / 分析方法
        n_levels: Number of levels per parameter / 每参数水平数

    Returns:
        Dict with sensitivity indices and ranking.
    """
    from core.design.sensitivity import sensitivity_oat, sensitivity_morris
    from core.simulation.simulator import run_simulation
    import numpy as np

    # Convert list ranges to tuple
    ranges = {k: (v[0], v[1]) for k, v in param_ranges.items()}

    # Default evaluation: simulate and return final water level
    def eval_fn(params: dict) -> float:
        tank_params = {k: v for k, v in params.items()}
        result = run_simulation(
            duration=300, dt=1.0, initial_h=0.5, tank_params=tank_params
        )
        return float(np.mean(result["water_level"]))

    if method == "OAT":
        return sensitivity_oat(base_params, ranges, eval_fn, n_levels=n_levels)
    elif method == "Morris":
        return sensitivity_morris(ranges, eval_fn, n_levels=n_levels)
    else:
        raise ValueError(f"Unknown method: {method}")


if __name__ == "__main__":
    mcp.run()
