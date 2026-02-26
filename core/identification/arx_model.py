"""ARX (Auto-Regressive with eXogenous input) model identification.
ARX 模型辨识 — 线性化后的离散传递函数辨识。

Model: y(k) = a1*y(k-1) + ... + ana*y(k-na) + b1*u(k-1) + ... + bnb*u(k-nb) + e(k)

Where:
    y: output (water level) / 输出（水位）
    u: input (inflow) / 输入（入流量）
    na: number of autoregressive terms / 自回归阶数
    nb: number of exogenous input terms / 外源输入阶数
"""

from __future__ import annotations

import numpy as np


def identify_arx(
    y: list[float],
    u: list[float],
    na: int = 2,
    nb: int = 2,
    nk: int = 1,
) -> dict:
    """Identify ARX model parameters using ordinary least squares.
    使用普通最小二乘法辨识 ARX 模型参数。

    Args:
        y: Output time series (water level) / 输出时序（水位）
        u: Input time series (inflow rate) / 输入时序（入流量）
        na: Autoregressive order / 自回归阶数
        nb: Exogenous input order / 外源输入阶数
        nk: Input delay / 输入延迟

    Returns:
        Dict with model coefficients, fit metrics, and prediction.
    """
    y_arr = np.array(y, dtype=float)
    u_arr = np.array(u, dtype=float)

    if len(y_arr) != len(u_arr):
        raise ValueError("y and u must have the same length")

    n = len(y_arr)
    max_lag = max(na, nb + nk - 1)
    if n <= max_lag:
        raise ValueError(f"Need at least {max_lag + 1} data points, got {n}")

    # Build regression matrix
    n_samples = n - max_lag
    n_params = na + nb
    phi = np.zeros((n_samples, n_params))
    y_target = np.zeros(n_samples)

    for i in range(n_samples):
        k = i + max_lag
        # Autoregressive terms: y(k-1), ..., y(k-na)
        for j in range(na):
            phi[i, j] = -y_arr[k - 1 - j]
        # Exogenous input terms: u(k-nk), ..., u(k-nk-nb+1)
        for j in range(nb):
            phi[i, na + j] = u_arr[k - nk - j]
        y_target[i] = y_arr[k]

    # OLS: theta = (Phi^T Phi)^{-1} Phi^T y
    theta, residuals_arr, rank, sv = np.linalg.lstsq(phi, y_target, rcond=None)

    # Extract coefficients
    a_coeffs = theta[:na].tolist()
    b_coeffs = theta[na:].tolist()

    # Compute fit metrics
    y_pred = phi @ theta
    ss_res = np.sum((y_target - y_pred) ** 2)
    ss_tot = np.sum((y_target - np.mean(y_target)) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse = float(np.sqrt(np.mean((y_target - y_pred) ** 2)))

    return {
        "a_coefficients": a_coeffs,
        "b_coefficients": b_coeffs,
        "na": na,
        "nb": nb,
        "nk": nk,
        "r_squared": float(r_squared),
        "rmse": rmse,
        "n_samples": n_samples,
        "predicted": y_pred.tolist(),
    }


def predict_arx(
    model: dict,
    y_history: list[float],
    u_future: list[float],
) -> list[float]:
    """Predict future outputs using an identified ARX model.
    使用辨识的 ARX 模型预测未来输出。

    Args:
        model: ARX model dict from identify_arx / 辨识结果字典
        y_history: Recent output history (length >= na) / 近期输出历史
        u_future: Future input sequence / 未来输入序列

    Returns:
        List of predicted outputs / 预测输出序列
    """
    a = model["a_coefficients"]
    b = model["b_coefficients"]
    na = model["na"]
    nb = model["nb"]
    nk = model["nk"]

    y_buf = list(y_history)
    u_buf = list(y_history[:0])  # empty initially, we prepend from history
    predictions = []

    for k, u_k in enumerate(u_future):
        y_k = 0.0
        for j in range(na):
            idx = len(y_buf) - 1 - j
            if idx >= 0:
                y_k -= a[j] * y_buf[idx]
        for j in range(nb):
            # u(k - nk - j): need historical u values
            u_idx = k - nk - j
            if 0 <= u_idx < len(u_future):
                y_k += b[j] * u_future[u_idx]
        y_buf.append(y_k)
        predictions.append(y_k)

    return predictions
