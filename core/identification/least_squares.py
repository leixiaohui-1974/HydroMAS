"""Least-squares parameter identification for tank models.
最小二乘法参数辨识。

Identifies tank parameters (Cd, outlet_area) from observed inflow/outflow/level data
by minimizing the residual between modeled and observed outflow.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares as scipy_least_squares

from core.simulation.tank_model import GRAVITY


def identify_tank_params(
    observed_h: list[float],
    observed_q_out: list[float],
    initial_guess: dict | None = None,
    bounds: dict | None = None,
) -> dict:
    """Identify Cd and outlet_area from observed data using nonlinear least squares.
    通过非线性最小二乘法从观测数据辨识 Cd 和出口面积。

    The outflow model: Q_out = Cd * a * sqrt(2 * g * h)
    We fit [Cd, a] to minimize sum((Q_out_model - Q_out_observed)^2).

    Args:
        observed_h: Observed water level time series (m) / 观测水位序列
        observed_q_out: Observed outflow time series (m³/s) / 观测出流序列
        initial_guess: Initial guess for {"cd": float, "outlet_area": float}
        bounds: Parameter bounds {"cd": (lo, hi), "outlet_area": (lo, hi)}

    Returns:
        Dict with identified parameters and fit quality metrics.
    """
    h_arr = np.array(observed_h)
    q_obs = np.array(observed_q_out)

    if len(h_arr) != len(q_obs):
        raise ValueError("observed_h and observed_q_out must have same length")
    if len(h_arr) < 2:
        raise ValueError("Need at least 2 data points for identification")

    guess = initial_guess or {}
    x0 = np.array([guess.get("cd", 0.6), guess.get("outlet_area", 0.01)])

    b = bounds or {}
    cd_bounds = b.get("cd", (0.01, 1.0))
    a_bounds = b.get("outlet_area", (1e-5, 0.1))
    lower = [cd_bounds[0], a_bounds[0]]
    upper = [cd_bounds[1], a_bounds[1]]

    # Pre-compute safe sqrt term outside residuals (called ~100x by optimizer)
    h_safe_sqrt = np.sqrt(2.0 * GRAVITY * np.maximum(h_arr, 0.0))

    def residuals(x: np.ndarray) -> np.ndarray:
        cd, a = x
        return cd * a * h_safe_sqrt - q_obs

    result = scipy_least_squares(residuals, x0, bounds=(lower, upper), method="trf")

    cd_fit, a_fit = result.x
    q_fitted = cd_fit * a_fit * h_safe_sqrt
    ss_res = np.sum((q_fitted - q_obs) ** 2)
    ss_tot = np.sum((q_obs - np.mean(q_obs)) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if not np.isclose(ss_tot, 0.0) else 0.0

    return {
        "cd": float(cd_fit),
        "outlet_area": float(a_fit),
        "r_squared": float(r_squared),
        "rmse": float(np.sqrt(np.mean((q_fitted - q_obs) ** 2))),
        "residual_norm": float(result.cost),
        "converged": bool(result.success),
        "message": result.message,
    }
