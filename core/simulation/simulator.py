"""Simulation runner — supports Euler, RK4, and scipy.integrate.odeint solvers.
仿真运行器 — 支持欧拉法、RK4 和 odeint 求解器。
"""

from __future__ import annotations

import bisect
from typing import Literal

import numpy as np

from core.simulation.tank_model import TankParams, compute_outflow, tank_ode


def _make_inflow_cache(q_in_profile: list[tuple[float, float]]) -> dict:
    """Pre-extract times/values for O(log n) interpolation."""
    return {
        "times": [p[0] for p in q_in_profile],
        "values": [p[1] for p in q_in_profile],
    }


def _interpolate_inflow(t: float, q_in_profile: list[tuple[float, float]],
                        _cache: dict | None = None) -> float:
    """Linearly interpolate inflow at time t from a profile (O(log n) via bisect).
    从入流时序中线性插值得到 t 时刻的入流量。

    Args:
        t: Time (s) / 时间
        q_in_profile: List of (time, Q_in) pairs / 入流时序
        _cache: Optional pre-extracted times/values for repeated calls

    Returns:
        Interpolated inflow rate (m³/s) / 插值后的入流量
    """
    if not q_in_profile:
        return 0.0
    if len(q_in_profile) == 1:
        return q_in_profile[0][1]

    if _cache is not None:
        times = _cache["times"]
        values = _cache["values"]
    else:
        times = [p[0] for p in q_in_profile]
        values = [p[1] for p in q_in_profile]

    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]

    # O(log n) bisect lookup
    i = bisect.bisect_right(times, t) - 1
    t0, q0 = times[i], values[i]
    t1, q1 = times[i + 1], values[i + 1]
    alpha = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
    return q0 + alpha * (q1 - q0)


def simulate_euler(
    duration: float,
    dt: float,
    q_in_profile: list[tuple[float, float]],
    initial_h: float,
    params: TankParams,
) -> dict:
    """Euler method simulation. / 欧拉法仿真。

    Args:
        duration: Simulation duration (s) / 仿真时长
        dt: Time step (s) / 时间步长
        q_in_profile: Inflow time series [(t, Q_in), ...] / 入流时序
        initial_h: Initial water level (m) / 初始水位
        params: Tank parameters / 水箱参数

    Returns:
        Dict with time, water_level, outflow, inflow arrays and metadata.
    """
    n_steps = round(duration / dt)
    time_arr = np.zeros(n_steps + 1)
    h_arr = np.zeros(n_steps + 1)
    qout_arr = np.zeros(n_steps + 1)
    qin_arr = np.zeros(n_steps + 1)

    cache = _make_inflow_cache(q_in_profile)

    h_arr[0] = initial_h
    time_arr[0] = 0.0
    qin_arr[0] = _interpolate_inflow(0.0, q_in_profile, cache)
    qout_arr[0] = compute_outflow(initial_h, params)

    for i in range(n_steps):
        t = i * dt
        q_in = _interpolate_inflow(t, q_in_profile, cache)
        dhdt = tank_ode(h_arr[i], q_in, params)
        h_new = h_arr[i] + dhdt * dt
        h_new = max(params.h_min, min(params.h_max, h_new))

        time_arr[i + 1] = t + dt
        h_arr[i + 1] = h_new
        qin_arr[i + 1] = _interpolate_inflow(t + dt, q_in_profile, cache)
        qout_arr[i + 1] = compute_outflow(h_new, params)

    return {
        "time": time_arr.tolist(),
        "water_level": h_arr.tolist(),
        "outflow": qout_arr.tolist(),
        "inflow": qin_arr.tolist(),
        "metadata": {"solver": "Euler", "steps": n_steps, "dt": dt},
    }


def simulate_rk4(
    duration: float,
    dt: float,
    q_in_profile: list[tuple[float, float]],
    initial_h: float,
    params: TankParams,
) -> dict:
    """4th-order Runge-Kutta simulation. / RK4 仿真。

    Args:
        duration: Simulation duration (s) / 仿真时长
        dt: Time step (s) / 时间步长
        q_in_profile: Inflow time series [(t, Q_in), ...] / 入流时序
        initial_h: Initial water level (m) / 初始水位
        params: Tank parameters / 水箱参数

    Returns:
        Dict with time, water_level, outflow, inflow arrays and metadata.
    """
    n_steps = round(duration / dt)
    time_arr = np.zeros(n_steps + 1)
    h_arr = np.zeros(n_steps + 1)
    qout_arr = np.zeros(n_steps + 1)
    qin_arr = np.zeros(n_steps + 1)

    cache = _make_inflow_cache(q_in_profile)

    h_arr[0] = initial_h
    time_arr[0] = 0.0
    qin_arr[0] = _interpolate_inflow(0.0, q_in_profile, cache)
    qout_arr[0] = compute_outflow(initial_h, params)

    for i in range(n_steps):
        t = i * dt
        h = h_arr[i]
        q_in = _interpolate_inflow(t, q_in_profile, cache)
        q_in_mid = _interpolate_inflow(t + dt / 2, q_in_profile, cache)
        q_in_end = _interpolate_inflow(t + dt, q_in_profile, cache)

        k1 = tank_ode(h, q_in, params)
        k2 = tank_ode(h + 0.5 * dt * k1, q_in_mid, params)
        k3 = tank_ode(h + 0.5 * dt * k2, q_in_mid, params)
        k4 = tank_ode(h + dt * k3, q_in_end, params)

        h_new = h + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        h_new = max(params.h_min, min(params.h_max, h_new))

        time_arr[i + 1] = t + dt
        h_arr[i + 1] = h_new
        qin_arr[i + 1] = _interpolate_inflow(t + dt, q_in_profile, cache)
        qout_arr[i + 1] = compute_outflow(h_new, params)

    return {
        "time": time_arr.tolist(),
        "water_level": h_arr.tolist(),
        "outflow": qout_arr.tolist(),
        "inflow": qin_arr.tolist(),
        "metadata": {"solver": "RK4", "steps": n_steps, "dt": dt},
    }


def run_simulation(
    duration: float,
    dt: float = 1.0,
    q_in_profile: list[tuple[float, float]] | None = None,
    initial_h: float = 0.5,
    tank_params: dict | None = None,
    solver: Literal["euler", "rk4"] = "rk4",
) -> dict:
    """Run a tank simulation with the specified solver.
    使用指定求解器运行水箱仿真。

    Args:
        duration: Simulation duration (s) / 仿真时长
        dt: Time step (s) / 时间步长
        q_in_profile: Inflow profile [(t, Q_in), ...]; defaults to constant 0.01 m³/s
        initial_h: Initial water level (m) / 初始水位
        tank_params: Optional dict of TankParams overrides / 水箱参数覆盖
        solver: Solver type ("euler" or "rk4") / 求解器类型

    Returns:
        Simulation result dict with time, water_level, outflow, inflow arrays.

    Raises:
        ValueError: If dt <= 0, duration <= 0, or step count exceeds 10,000,000.
    """
    if dt <= 0:
        raise ValueError(f"dt must be positive, got {dt}")
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")

    max_steps = 10_000_000
    if round(duration / dt) > max_steps:
        raise ValueError(
            f"Simulation would require {round(duration / dt)} steps "
            f"(duration={duration}, dt={dt}), exceeding limit of {max_steps}"
        )

    params = TankParams(**(tank_params or {}))
    params.validate()

    if q_in_profile is None:
        q_in_profile = [(0.0, 0.01), (duration, 0.01)]

    if solver == "euler":
        return simulate_euler(duration, dt, q_in_profile, initial_h, params)
    elif solver == "rk4":
        return simulate_rk4(duration, dt, q_in_profile, initial_h, params)
    else:
        raise ValueError(f"Unknown solver: {solver}. Choose 'euler' or 'rk4'.")
