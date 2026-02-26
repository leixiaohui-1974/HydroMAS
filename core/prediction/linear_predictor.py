"""Linear predictor for time series forecasting.
线性预测器 — 基于线性回归的时序预测。

Uses recent history to fit a linear trend and extrapolate.
"""

from __future__ import annotations

import numpy as np


def predict_linear(
    historical_data: list[float],
    horizon: int = 60,
    lookback: int | None = None,
) -> dict:
    """Predict future values using linear regression on recent history.
    使用线性回归预测未来值。

    Args:
        historical_data: Historical time series / 历史时序数据
        horizon: Number of future steps to predict / 预测步数
        lookback: Number of recent points to use for fitting (default: all) / 回看窗口

    Returns:
        Dict with predictions, trend parameters, and backtest results.
    """
    data = np.array(historical_data, dtype=float)

    if len(data) < 2:
        raise ValueError("Need at least 2 data points for linear prediction")

    if lookback is not None and lookback < len(data):
        data = data[-lookback:]

    n = len(data)
    x = np.arange(n, dtype=float)

    # Linear regression: y = slope * x + intercept
    coeffs = np.polyfit(x, data, deg=1)
    slope, intercept = coeffs

    # Backtest: fit on data
    fitted = slope * x + intercept
    residuals = data - fitted

    # Predict future
    future_x = np.arange(n, n + horizon, dtype=float)
    predictions = slope * future_x + intercept

    # Confidence interval (simple ±2σ of residuals)
    residual_std = float(np.std(residuals))
    upper = (predictions + 2 * residual_std).tolist()
    lower = (predictions - 2 * residual_std).tolist()

    return {
        "predictions": predictions.tolist(),
        "confidence_upper": upper,
        "confidence_lower": lower,
        "slope": float(slope),
        "intercept": float(intercept),
        "residual_std": residual_std,
        "backtest_fitted": fitted.tolist(),
        "backtest_residuals": residuals.tolist(),
        "horizon": horizon,
        "method": "linear",
    }


def predict_polynomial(
    historical_data: list[float],
    horizon: int = 60,
    degree: int = 2,
    lookback: int | None = None,
) -> dict:
    """Predict future values using polynomial regression.
    使用多项式回归预测未来值。

    Args:
        historical_data: Historical time series / 历史时序数据
        horizon: Number of future steps / 预测步数
        degree: Polynomial degree / 多项式阶数
        lookback: Number of recent points to use / 回看窗口

    Returns:
        Dict with predictions and fit metrics.
    """
    data = np.array(historical_data, dtype=float)

    if len(data) < degree + 1:
        raise ValueError(f"Need at least {degree + 1} points for degree-{degree} polynomial")

    if lookback is not None and lookback < len(data):
        data = data[-lookback:]

    n = len(data)
    x = np.arange(n, dtype=float)

    coeffs = np.polyfit(x, data, deg=degree)
    poly = np.poly1d(coeffs)

    fitted = poly(x)
    residuals = data - fitted
    residual_std = float(np.std(residuals))

    future_x = np.arange(n, n + horizon, dtype=float)
    predictions = poly(future_x)

    return {
        "predictions": predictions.tolist(),
        "confidence_upper": (predictions + 2 * residual_std).tolist(),
        "confidence_lower": (predictions - 2 * residual_std).tolist(),
        "coefficients": coeffs.tolist(),
        "residual_std": residual_std,
        "backtest_fitted": fitted.tolist(),
        "horizon": horizon,
        "degree": degree,
        "method": f"polynomial_deg{degree}",
    }
