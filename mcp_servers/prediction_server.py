"""MCP Server: Prediction tools for water level forecasting.
MCP 服务器：水位预测工具。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Prediction")


@mcp.tool()
def predict_future(
    historical_data: list[float],
    horizon: int = 60,
    model: str = "linear",
    lookback: int | None = None,
    degree: int = 2,
) -> dict:
    """Predict future water levels based on historical data.
    基于历史数据预测未来水位。

    Args:
        historical_data: Historical time series / 历史时序
        horizon: Number of future steps to predict / 预测步数
        model: Prediction model ("linear", "polynomial", "lstm") / 预测模型
        lookback: Number of recent points to use / 回看窗口
        degree: Polynomial degree (only used when model="polynomial") / 多项式阶数

    Returns:
        Dict with predictions, confidence intervals, and fit metrics.
    """
    if not historical_data:
        raise ValueError("historical_data cannot be empty")
    if horizon <= 0:
        raise ValueError(f"horizon must be positive, got {horizon}")

    if model == "linear":
        from core.prediction.linear_predictor import predict_linear
        return predict_linear(historical_data, horizon=horizon, lookback=lookback)
    elif model == "polynomial":
        from core.prediction.linear_predictor import predict_polynomial
        return predict_polynomial(historical_data, horizon=horizon, lookback=lookback, degree=degree)
    elif model == "lstm":
        from core.prediction.lstm_predictor import predict_lstm
        return predict_lstm(historical_data, horizon=horizon)
    else:
        raise ValueError(f"Unknown model: {model}. Use 'linear', 'polynomial', or 'lstm'.")


if __name__ == "__main__":
    mcp.run()
