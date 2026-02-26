"""Tank sizing optimization.
水箱尺寸优化。

Determines optimal tank dimensions (area, outlet size) given requirements
(demand profile, safety constraints, cost model).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize


def optimize_tank_size(
    peak_demand: float = 0.02,
    min_reserve_time: float = 300.0,
    max_area: float = 10.0,
    max_height: float = 3.0,
    cost_per_m2: float = 1000.0,
    cost_per_m_height: float = 500.0,
) -> dict:
    """Optimize tank area and height to minimize cost while meeting demand.
    优化水箱面积和高度，在满足需求的同时最小化成本。

    Constraints:
        - Volume >= peak_demand * min_reserve_time (reserve capacity)
        - Area <= max_area
        - Height <= max_height

    Args:
        peak_demand: Peak outflow demand (m³/s) / 峰值需水量
        min_reserve_time: Minimum reserve time at peak demand (s) / 最小储备时长
        max_area: Maximum tank area (m²) / 最大水箱面积
        max_height: Maximum tank height (m) / 最大水箱高度
        cost_per_m2: Cost per unit area ($/m²) / 单位面积成本
        cost_per_m_height: Cost per unit height ($/m) / 单位高度成本

    Returns:
        Dict with optimal dimensions, cost, and capacity.
    """
    required_volume = peak_demand * min_reserve_time

    def cost(x: np.ndarray) -> float:
        area, height = x
        return cost_per_m2 * area + cost_per_m_height * height

    def volume_constraint(x: np.ndarray) -> float:
        area, height = x
        return area * height - required_volume

    x0 = np.array([max_area / 2, max_height / 2])
    bounds = [(0.1, max_area), (0.1, max_height)]
    constraints = [{"type": "ineq", "fun": volume_constraint}]

    result = minimize(cost, x0, method="SLSQP", bounds=bounds, constraints=constraints)

    if not result.success:
        # Fallback: compute minimum area for given height
        area = required_volume / max_height
        height = max_height
        return {
            "status": "fallback",
            "optimal_area": float(area),
            "optimal_height": float(height),
            "volume": float(area * height),
            "cost": cost_per_m2 * area + cost_per_m_height * height,
            "required_volume": required_volume,
        }

    opt_area, opt_height = result.x
    return {
        "status": "optimal",
        "optimal_area": float(opt_area),
        "optimal_height": float(opt_height),
        "volume": float(opt_area * opt_height),
        "cost": float(result.fun),
        "required_volume": required_volume,
        "peak_demand": peak_demand,
        "reserve_time": min_reserve_time,
    }
