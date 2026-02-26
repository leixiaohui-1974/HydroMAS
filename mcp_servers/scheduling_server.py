"""MCP Server: Scheduling optimization tools.
MCP 服务器：调度优化工具。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Scheduling")


@mcp.tool()
def optimize_schedule(
    demand_forecast: list[float],
    supply_capacity: float = 0.05,
    constraints: dict | None = None,
    objective: str = "minimize_cost",
    method: str = "lp",
) -> dict:
    """Optimize inflow schedule to meet demands within constraints.
    优化入流调度以在约束条件下满足需求。

    Args:
        demand_forecast: Expected outflow/demand per period (m³/s) / 各时段需求
        supply_capacity: Maximum inflow rate (m³/s) / 最大供水能力
        constraints: Additional constraints {min_level, max_level, initial_level, ...} / 附加约束
        objective: "minimize_cost" or "maximize_supply" / 优化目标
        method: "lp" (linear programming) or "rule" (rule-based) / 方法

    Returns:
        Dict with optimal schedule and metadata.
    """
    if not demand_forecast:
        raise ValueError("demand_forecast cannot be empty")
    if supply_capacity <= 0:
        raise ValueError(f"supply_capacity must be positive, got {supply_capacity}")

    c = constraints or {}

    if method == "lp":
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        return optimize_schedule_lp(
            demand_forecast=demand_forecast,
            supply_capacity=supply_capacity,
            min_level=c.get("min_level", 0.2),
            max_level=c.get("max_level", 1.8),
            initial_level=c.get("initial_level", 0.5),
            tank_area=c.get("tank_area", 1.0),
            dt=c.get("dt", 60.0),
            objective=objective,
        )
    elif method == "rule":
        from core.scheduling.rule_based import schedule_rule_based
        return schedule_rule_based(
            current_level=c.get("current_level", 0.5),
            target_level=c.get("target_level", 1.0),
            supply_capacity=supply_capacity,
            current_demand=demand_forecast[0] if demand_forecast else 0.01,
        )
    else:
        raise ValueError(f"Unknown method: {method}")


if __name__ == "__main__":
    mcp.run()
