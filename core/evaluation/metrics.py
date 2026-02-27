"""Performance evaluation metrics for water system analysis.
水系统性能评价指标。

Includes: RMSE, MAE, NSE (Nash-Sutcliffe Efficiency), MAPE,
          response time, overshoot, settling time, steady-state error.
"""

from __future__ import annotations

import numpy as np


def rmse(observed: list[float], predicted: list[float]) -> float:
    """Root Mean Square Error. / 均方根误差。

    Args:
        observed: Observed values / 观测值
        predicted: Predicted/simulated values / 预测/仿真值

    Returns:
        RMSE value.
    """
    o = np.array(observed)
    p = np.array(predicted)
    return float(np.sqrt(np.mean((o - p) ** 2)))


def mae(observed: list[float], predicted: list[float]) -> float:
    """Mean Absolute Error. / 平均绝对误差。

    Args:
        observed: Observed values / 观测值
        predicted: Predicted values / 预测值

    Returns:
        MAE value.
    """
    o = np.array(observed)
    p = np.array(predicted)
    return float(np.mean(np.abs(o - p)))


def nse(observed: list[float], predicted: list[float]) -> float:
    """Nash-Sutcliffe Efficiency. / 纳什效率系数。

    NSE = 1 - Σ(obs - pred)² / Σ(obs - mean(obs))²
    Perfect score = 1.0, negative = worse than mean.

    Args:
        observed: Observed values / 观测值
        predicted: Predicted values / 预测值

    Returns:
        NSE value in (-inf, 1].
    """
    o = np.array(observed)
    p = np.array(predicted)
    ss_res = np.sum((o - p) ** 2)
    ss_tot = np.sum((o - np.mean(o)) ** 2)
    if ss_tot == 0:
        # All observed values identical: perfect match → 1.0, else large negative
        return 1.0 if ss_res == 0 else -1e6
    return float(1.0 - ss_res / ss_tot)


def mape(observed: list[float], predicted: list[float]) -> float:
    """Mean Absolute Percentage Error. / 平均绝对百分比误差。

    Args:
        observed: Observed values (non-zero) / 观测值（非零）
        predicted: Predicted values / 预测值

    Returns:
        MAPE as a percentage (0-100+).
    """
    o = np.array(observed)
    p = np.array(predicted)
    mask = o != 0
    if not np.any(mask):
        return float("inf")
    return float(np.mean(np.abs((o[mask] - p[mask]) / o[mask])) * 100)


def settling_time(
    time_series: list[float],
    value_series: list[float],
    setpoint: float,
    tolerance: float = 0.02,
) -> float | None:
    """Compute settling time (time to reach and stay within tolerance of setpoint).
    计算调节时间（达到并保持在设定值容差范围内的时间）。

    Args:
        time_series: Time values / 时间序列
        value_series: Response values / 响应值序列
        setpoint: Target value / 目标值
        tolerance: Fraction of setpoint for settling band / 稳态容差比例

    Returns:
        Settling time (s) or None if not settled.
    """
    if tolerance <= 0:
        raise ValueError(f"tolerance must be positive, got {tolerance}")
    band = abs(setpoint * tolerance) if setpoint != 0 else tolerance
    t = np.array(time_series)
    v = np.array(value_series)

    # Find the last index where the value is outside the settling band.
    # Settling time = time at the first sample AFTER which the value never
    # leaves the band again (i.e., stays within for all remaining samples).
    outside = np.abs(v - setpoint) > band
    if not np.any(outside):
        return 0.0  # always within band

    last_outside_idx = int(np.where(outside)[0][-1])
    if last_outside_idx + 1 >= len(t):
        return None  # never settled (last sample is still outside)

    return float(t[last_outside_idx + 1])


def overshoot(value_series: list[float], setpoint: float) -> float:
    """Compute maximum overshoot as percentage of setpoint.
    计算最大超调量（设定值的百分比）。

    Args:
        value_series: Response values / 响应值序列
        setpoint: Target value / 目标值

    Returns:
        Overshoot percentage (%).
    """
    v = np.array(value_series)
    setpoint_abs = abs(setpoint)
    if setpoint_abs < 1e-10:
        return 0.0

    max_val = np.max(v)
    if max_val <= setpoint:
        return 0.0

    return float((max_val - setpoint) / setpoint_abs * 100)


def steady_state_error(value_series: list[float], setpoint: float, n_tail: int = 10) -> float:
    """Compute steady-state error (average of last n_tail points minus setpoint).
    计算稳态误差。

    Args:
        value_series: Response values / 响应值序列
        setpoint: Target value / 目标值
        n_tail: Number of trailing points to average / 末尾平均点数

    Returns:
        Steady-state error.
    """
    if n_tail <= 0:
        raise ValueError(f"n_tail must be positive, got {n_tail}")
    v = np.array(value_series)
    tail = v[-n_tail:] if len(v) >= n_tail else v
    return float(np.mean(tail) - setpoint)


def evaluate_performance(
    observed: list[float],
    predicted: list[float],
    metrics_list: list[str] | None = None,
    time_series: list[float] | None = None,
    setpoint: float | None = None,
) -> dict:
    """Evaluate performance using multiple metrics.
    使用多个指标评估性能。

    Args:
        observed: Observed/reference values / 观测/参考值
        predicted: Predicted/simulated values / 预测/仿真值
        metrics_list: Which metrics to compute / 需要计算的指标列表
        time_series: Time values (for settling_time) / 时间序列
        setpoint: Target value (for control metrics) / 目标值

    Returns:
        Dict of metric name to value.
    """
    if metrics_list is None:
        metrics_list = ["RMSE", "MAE", "NSE"]

    # Convert once, reuse across all metrics to avoid redundant np.array() calls
    obs_arr = np.asarray(observed, dtype=float)
    pred_arr = np.asarray(predicted, dtype=float)

    results = {}
    metric_map = {
        "RMSE": lambda: rmse(obs_arr, pred_arr),
        "MAE": lambda: mae(obs_arr, pred_arr),
        "NSE": lambda: nse(obs_arr, pred_arr),
        "MAPE": lambda: mape(obs_arr, pred_arr),
    }

    for m in metrics_list:
        m_upper = m.upper()
        if m_upper in metric_map:
            results[m_upper] = metric_map[m_upper]()
        elif m_upper == "SETTLING_TIME" and time_series and setpoint is not None:
            results["SETTLING_TIME"] = settling_time(time_series, predicted, setpoint)
        elif m_upper == "OVERSHOOT" and setpoint is not None:
            results["OVERSHOOT"] = overshoot(predicted, setpoint)
        elif m_upper == "STEADY_STATE_ERROR" and setpoint is not None:
            results["STEADY_STATE_ERROR"] = steady_state_error(predicted, setpoint)

    return results
