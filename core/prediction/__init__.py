"""Core prediction module — time series forecasting.
核心预测模块 — 时序预测。
"""

from core.prediction.linear_predictor import (
    predict_linear,
    predict_polynomial,
)

__all__ = [
    "predict_linear",
    "predict_polynomial",
]
