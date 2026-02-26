"""LSTM predictor stub for time series forecasting.
LSTM 预测器存根 — 需要安装 torch 可选依赖。

This module provides a placeholder API. Full LSTM implementation
requires the 'lstm' optional dependency group (torch).
"""

from __future__ import annotations


def predict_lstm(
    historical_data: list[float],
    horizon: int = 60,
    hidden_size: int = 32,
    epochs: int = 50,
) -> dict:
    """Predict future values using LSTM (requires torch).
    使用 LSTM 预测未来值（需要 torch）。

    Args:
        historical_data: Historical time series / 历史时序数据
        horizon: Number of future steps / 预测步数
        hidden_size: LSTM hidden layer size / LSTM 隐藏层大小
        epochs: Training epochs / 训练轮数

    Returns:
        Dict with predictions or error if torch unavailable.
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        return {
            "error": "torch not installed. Install with: pip install 'hydroos-agent[lstm]'",
            "predictions": [],
            "method": "lstm",
        }

    # Placeholder — full LSTM implementation for future expansion
    # LSTM 完整实现将在扩展阶段完成
    return {
        "error": "LSTM predictor not yet implemented",
        "predictions": [],
        "method": "lstm",
    }
