"""Linear programming scheduler for inflow optimization.
线性规划调度器 — 入流分配优化。

Uses PuLP to solve LP/MILP problems for optimal water scheduling.
"""

from __future__ import annotations


def optimize_schedule_lp(
    demand_forecast: list[float],
    supply_capacity: float,
    n_periods: int | None = None,
    min_level: float = 0.2,
    max_level: float = 1.8,
    initial_level: float = 0.5,
    tank_area: float = 1.0,
    dt: float = 60.0,
    objective: str = "minimize_cost",
) -> dict:
    """Optimize inflow schedule using linear programming.
    使用线性规划优化入流调度。

    Minimizes total inflow (proxy for cost/energy) while meeting demands
    and respecting tank level constraints.

    Args:
        demand_forecast: Expected outflow/demand per period (m³/s) / 各时段需求预测
        supply_capacity: Maximum inflow rate (m³/s) / 最大入流能力
        n_periods: Number of scheduling periods / 调度时段数
        min_level: Minimum allowed water level (m) / 最低允许水位
        max_level: Maximum allowed water level (m) / 最高允许水位
        initial_level: Starting water level (m) / 初始水位
        tank_area: Tank cross-section area (m²) / 水箱截面积
        dt: Time step per period (s) / 每时段时长
        objective: Optimization objective / 优化目标

    Returns:
        Dict with optimal schedule and metadata.
    """
    if not demand_forecast:
        raise ValueError("demand_forecast cannot be empty")
    if supply_capacity <= 0:
        raise ValueError(f"supply_capacity must be positive, got {supply_capacity}")
    if initial_level < min_level or initial_level > max_level:
        raise ValueError(
            f"initial_level ({initial_level}) must be between "
            f"min_level ({min_level}) and max_level ({max_level})"
        )

    try:
        import pulp
    except ImportError:
        return _fallback_schedule(demand_forecast, supply_capacity)

    if n_periods is None:
        n_periods = len(demand_forecast)

    # Decision variables: inflow rate per period
    q_in = [
        pulp.LpVariable(f"q_in_{t}", lowBound=0, upBound=supply_capacity)
        for t in range(n_periods)
    ]

    # Level tracking variables
    h = [
        pulp.LpVariable(f"h_{t}", lowBound=min_level, upBound=max_level)
        for t in range(n_periods + 1)
    ]

    # Problem definition
    prob = pulp.LpProblem("water_schedule", pulp.LpMinimize)

    # Objective
    if objective == "maximize_supply":
        prob += -pulp.lpSum(q_in)  # maximize by negating
    else:
        prob += pulp.lpSum(q_in)   # minimize total inflow (cost proxy)

    # Initial condition
    prob += h[0] == initial_level

    # Mass balance constraints: h(t+1) = h(t) + (q_in(t) - demand(t)) * dt / A
    for t in range(n_periods):
        demand = demand_forecast[t] if t < len(demand_forecast) else demand_forecast[-1]
        prob += h[t + 1] == h[t] + (q_in[t] - demand) * dt / tank_area

    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if prob.status != pulp.constants.LpStatusOptimal:
        status_name = pulp.LpStatus.get(prob.status, "unknown")
        return {
            "status": "infeasible" if prob.status == -1 else "solver_error",
            "schedule": [],
            "message": f"No feasible schedule found (solver: {status_name})",
        }

    schedule = [float(v.varValue) if v.varValue is not None else 0.0 for v in q_in]
    levels = [float(v.varValue) if v.varValue is not None else 0.0 for v in h]

    return {
        "status": "optimal",
        "schedule": schedule,
        "inflow_rate": schedule,
        "predicted_levels": levels,
        "total_inflow": float(sum(schedule)),
        "objective_value": float(pulp.value(prob.objective)),
        "n_periods": n_periods,
        "method": "linear_programming",
    }


def _fallback_schedule(
    demand_forecast: list[float],
    supply_capacity: float,
) -> dict:
    """Simple fallback when PuLP is not available.
    PuLP 不可用时的简单回退方案。
    """
    schedule = [min(d * 1.1, supply_capacity) for d in demand_forecast]
    return {
        "status": "fallback",
        "schedule": schedule,
        "message": "PuLP not installed; using simple demand-tracking schedule",
        "method": "fallback",
    }
