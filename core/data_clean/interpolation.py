"""Missing value interpolation methods for time series.
时序数据缺失值插补方法。

Methods:
    - Linear interpolation / 线性插值
    - Spline interpolation / 样条插值
    - Median filter (for noise reduction) / 中值滤波（降噪）
"""

from __future__ import annotations

import numpy as np
from scipy import interpolate as sci_interp


def interpolate_linear(data: list[float]) -> dict:
    """Fill missing values (NaN) using linear interpolation.
    使用线性插值填补缺失值。

    Args:
        data: Time series with possible NaN values / 含缺失值的时序

    Returns:
        Dict with filled data and metadata.
    """
    arr = np.array(data, dtype=float)
    nan_mask = np.isnan(arr)
    n_missing = int(np.sum(nan_mask))

    if n_missing == 0:
        return {"data": arr.tolist(), "n_filled": 0, "method": "linear"}

    if n_missing == len(arr):
        return {"data": [0.0] * len(arr), "n_filled": n_missing, "method": "linear"}

    indices = np.arange(len(arr))
    valid_mask = ~nan_mask
    arr[nan_mask] = np.interp(indices[nan_mask], indices[valid_mask], arr[valid_mask])

    return {"data": arr.tolist(), "n_filled": n_missing, "method": "linear"}


def interpolate_spline(data: list[float], order: int = 3) -> dict:
    """Fill missing values using spline interpolation.
    使用样条插值填补缺失值。

    Args:
        data: Time series with possible NaN values / 含缺失值的时序
        order: Spline order (default 3 = cubic) / 样条阶数

    Returns:
        Dict with filled data and metadata.
    """
    arr = np.array(data, dtype=float)
    nan_mask = np.isnan(arr)
    n_missing = int(np.sum(nan_mask))

    if n_missing == 0:
        return {"data": arr.tolist(), "n_filled": 0, "method": f"spline_k{order}"}

    valid_mask = ~nan_mask
    n_valid = int(np.sum(valid_mask))

    if n_valid < order + 1:
        # Fall back to linear if not enough points for spline
        return interpolate_linear(data)

    indices = np.arange(len(arr))
    spline = sci_interp.UnivariateSpline(
        indices[valid_mask], arr[valid_mask], k=order, s=0
    )
    arr[nan_mask] = spline(indices[nan_mask])

    return {"data": arr.tolist(), "n_filled": n_missing, "method": f"spline_k{order}"}


def median_filter(data: list[float], window_size: int = 5) -> dict:
    """Apply median filter for noise reduction.
    中值滤波降噪。

    Args:
        data: Input time series / 输入时序
        window_size: Filter window size (must be odd) / 滤波窗口大小（须为奇数）

    Returns:
        Dict with filtered data and metadata.
    """
    if window_size <= 0:
        raise ValueError(f"window_size must be positive, got {window_size}")
    if window_size % 2 == 0:
        window_size += 1

    arr = np.array(data, dtype=float)

    if not np.any(np.isnan(arr)):
        # Fast path: no NaN — use scipy's C implementation
        from scipy.ndimage import median_filter as _scipy_medfilt
        result = _scipy_medfilt(arr, size=window_size)
    else:
        # NaN-aware fallback
        n = len(arr)
        result = np.copy(arr)
        half = window_size // 2
        for i in range(n):
            lo = max(0, i - half)
            hi = min(n, i + half + 1)
            window = arr[lo:hi]
            valid = window[~np.isnan(window)]
            if len(valid) > 0:
                result[i] = np.median(valid)

    return {
        "data": result.tolist(),
        "window_size": window_size,
        "method": "median_filter",
    }


def clean_timeseries(
    raw_data: list[float],
    methods: list[str] | None = None,
) -> dict:
    """Apply a pipeline of cleaning methods to time series data.
    对时序数据应用一系列清洗方法。

    Args:
        raw_data: Raw time series / 原始时序
        methods: List of method names to apply in order / 按序应用的方法列表
            Options: "outlier_3sigma", "outlier_iqr", "interpolate_linear",
                     "interpolate_spline", "median_filter"

    Returns:
        Dict with cleaned data and applied steps.
    """
    if methods is None:
        methods = ["outlier_3sigma", "interpolate_linear"]

    from core.data_clean.outlier_detect import detect_3sigma, detect_iqr

    data = list(raw_data)
    steps = []

    for method in methods:
        if method == "outlier_3sigma":
            result = detect_3sigma(data)
            # Replace outliers with NaN
            for idx in result["outlier_indices"]:
                data[idx] = float("nan")
            steps.append({"method": method, "n_outliers": result["n_outliers"]})

        elif method == "outlier_iqr":
            result = detect_iqr(data)
            for idx in result["outlier_indices"]:
                data[idx] = float("nan")
            steps.append({"method": method, "n_outliers": result["n_outliers"]})

        elif method == "interpolate_linear":
            result = interpolate_linear(data)
            data = result["data"]
            steps.append({"method": method, "n_filled": result["n_filled"]})

        elif method == "interpolate_spline":
            result = interpolate_spline(data)
            data = result["data"]
            steps.append({"method": method, "n_filled": result["n_filled"]})

        elif method == "median_filter":
            result = median_filter(data)
            data = result["data"]
            steps.append({"method": method, "window_size": result["window_size"]})

        else:
            raise ValueError(f"Unknown cleaning method: {method}")

    return {"data": data, "steps": steps}
