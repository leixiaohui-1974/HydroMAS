"""Outlier detection methods for time series data.
时序数据异常值检测方法。

Methods:
    - 3-sigma rule / 3σ 规则
    - IQR (Interquartile Range) / 四分位距法
    - Median absolute deviation (MAD) / 中位数绝对偏差
"""

from __future__ import annotations

import numpy as np


def detect_3sigma(data: list[float], threshold: float = 3.0) -> dict:
    """Detect outliers using the 3-sigma rule.
    使用 3σ 规则检测异常值。

    Args:
        data: Input time series / 输入时序
        threshold: Number of standard deviations (default 3.0) / 标准差倍数

    Returns:
        Dict with outlier indices, mask, and cleaned values.
    """
    arr = np.array(data, dtype=float)
    mean = np.nanmean(arr)
    std = np.nanstd(arr)

    if np.isclose(std, 0.0):
        return {
            "outlier_indices": [],
            "mask": [False] * len(data),
            "n_outliers": 0,
            "bounds": {"lower": float(mean), "upper": float(mean)},
        }

    lower = mean - threshold * std
    upper = mean + threshold * std
    mask = (arr < lower) | (arr > upper) | np.isnan(arr)

    return {
        "outlier_indices": np.where(mask)[0].tolist(),
        "mask": mask.tolist(),
        "n_outliers": int(np.sum(mask)),
        "bounds": {"lower": float(lower), "upper": float(upper)},
    }


def detect_iqr(data: list[float], factor: float = 1.5) -> dict:
    """Detect outliers using the IQR method.
    使用四分位距法检测异常值。

    Args:
        data: Input time series / 输入时序
        factor: IQR multiplier (default 1.5) / IQR 倍数

    Returns:
        Dict with outlier indices, mask, and bounds.
    """
    arr = np.array(data, dtype=float)
    valid = arr[~np.isnan(arr)]

    if len(valid) == 0:
        return {
            "outlier_indices": list(range(len(data))),
            "mask": [True] * len(data),
            "n_outliers": len(data),
            "bounds": {"lower": 0.0, "upper": 0.0},
        }

    q1 = float(np.percentile(valid, 25))
    q3 = float(np.percentile(valid, 75))
    iqr = q3 - q1
    lower = q1 - factor * iqr
    upper = q3 + factor * iqr

    mask = (arr < lower) | (arr > upper) | np.isnan(arr)

    return {
        "outlier_indices": np.where(mask)[0].tolist(),
        "mask": mask.tolist(),
        "n_outliers": int(np.sum(mask)),
        "bounds": {"lower": lower, "upper": upper},
    }


def detect_mad(data: list[float], threshold: float = 3.5) -> dict:
    """Detect outliers using Median Absolute Deviation.
    使用中位数绝对偏差检测异常值。

    Args:
        data: Input time series / 输入时序
        threshold: MAD threshold (default 3.5) / MAD 阈值

    Returns:
        Dict with outlier indices and mask.
    """
    arr = np.array(data, dtype=float)

    # Handle all-NaN case early
    if np.all(np.isnan(arr)):
        return {
            "outlier_indices": list(range(len(data))),
            "mask": [True] * len(data),
            "n_outliers": len(data),
            "bounds": {"lower": 0.0, "upper": 0.0},
        }

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(arr)
        mad = np.nanmedian(np.abs(arr - median))

    if np.isclose(mad, 0.0):
        # When MAD is 0 (>50% identical values), fall back to mean absolute deviation
        mad = np.nanmean(np.abs(arr - median))
        if np.isclose(mad, 0.0):
            # All values truly identical — no outliers
            return {
                "outlier_indices": [],
                "mask": [False] * len(data),
                "n_outliers": 0,
                "bounds": {"lower": float(median), "upper": float(median)},
            }

    # Modified Z-score
    modified_z = 0.6745 * (arr - median) / mad
    mask = (np.abs(modified_z) > threshold) | np.isnan(arr)

    return {
        "outlier_indices": np.where(mask)[0].tolist(),
        "mask": mask.tolist(),
        "n_outliers": int(np.sum(mask)),
        "bounds": {
            "lower": float(median - threshold * mad / 0.6745),
            "upper": float(median + threshold * mad / 0.6745),
        },
    }
