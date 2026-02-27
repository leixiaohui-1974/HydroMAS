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

    # Build regression matrix (vectorized)
    n_samples = n - max_lag
    n_params = na + nb
    phi = np.zeros((n_samples, n_params))
    y_target = y_arr[max_lag:]

    # Autoregressive terms: y(k-1), ..., y(k-na)
    for j in range(na):
        phi[:, j] = -y_arr[max_lag - 1 - j : max_lag - 1 - j + n_samples]
    # Exogenous input terms: u(k-nk), ..., u(k-nk-nb+1)
    for j in range(nb):
        phi[:, na + j] = u_arr[max_lag - nk - j : max_lag - nk - j + n_samples]

    # OLS: theta = (Phi^T Phi)^{-1} Phi^T y
    theta, residuals_arr, rank, sv = np.linalg.lstsq(phi, y_target, rcond=None)

    # Extract coefficients
    a_coeffs = theta[:na].tolist()
    b_coeffs = theta[na:].tolist()

    # Compute fit metrics
    y_pred = phi @ theta
    ss_res = np.sum((y_target - y_pred) ** 2)
    ss_tot = np.sum((y_target - np.mean(y_target)) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if not np.isclose(ss_tot, 0.0) else 0.0
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
    u_history: list[float] | None = None,
) -> list[float]:
    """Predict future outputs using an identified ARX model.
    使用辨识的 ARX 模型预测未来输出。

    Args:
        model: ARX model dict from identify_arx / 辨识结果字典
        y_history: Recent output history (length >= na) / 近期输出历史
        u_future: Future input sequence / 未来输入序列
        u_history: Recent input history (length >= nb+nk-1) / 近期输入历史

    Returns:
        List of predicted outputs / 预测输出序列
    """
    a = model["a_coefficients"]
    b = model["b_coefficients"]
    na = model["na"]
    nb = model["nb"]
    nk = model["nk"]

    if len(y_history) < na:
        raise ValueError(
            f"y_history length ({len(y_history)}) must be >= na ({na})"
        )

    # Warn if u_history not provided but nk > 0 (first nk predictions miss exogenous input)
    if u_history is None and nk > 0:
        import warnings
        warnings.warn(
            f"u_history not provided but nk={nk}; first {nk} predictions "
            f"will have incomplete exogenous input contribution",
            stacklevel=2,
        )

    # Pre-allocate y buffer with history + space for predictions
    n_pred = len(u_future)
    n_hist = len(y_history)
    y_buf = np.zeros(n_hist + n_pred)
    y_buf[:n_hist] = y_history

    # Build combined u buffer: historical u followed by future u
    u_hist = u_history or []
    u_buf = np.concatenate([np.array(u_hist, dtype=float), np.array(u_future, dtype=float)])
    u_offset = len(u_hist)

    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    u_len = len(u_buf)

    for k in range(n_pred):
        y_k = 0.0
        buf_pos = n_hist + k
        for j in range(na):
            idx = buf_pos - 1 - j
            if idx >= 0:
                y_k -= a_arr[j] * y_buf[idx]
        for j in range(nb):
            u_idx = u_offset + k - nk - j
            if 0 <= u_idx < u_len:
                y_k += b_arr[j] * u_buf[u_idx]
        y_buf[buf_pos] = y_k

    return y_buf[n_hist:].tolist()
