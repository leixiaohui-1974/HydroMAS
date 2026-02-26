"""Core prediction module — time series forecasting.
核心预测模块 — 时序预测。
"""

from core.prediction.linear_predictor import (
    predict_linear,
    predict_polynomial,
)
from core.prediction.lstm_predictor import predict_lstm

__all__ = [
    "predict_linear",
    "predict_polynomial",
    "predict_lstm",
]
