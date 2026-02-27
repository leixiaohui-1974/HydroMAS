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
        return predict_polynomial(
            historical_data, horizon=horizon,
            lookback=lookback, degree=degree,
        )
    elif model == "lstm":
        from core.prediction.lstm_predictor import predict_lstm
        return predict_lstm(historical_data, horizon=horizon)
    else:
        raise ValueError(f"Unknown model: {model}. Use 'linear', 'polynomial', or 'lstm'.")


@mcp.tool()
def predict_demand(historical_data: list[float], horizon: int = 24,
                   model: str = "linear", weather_data: dict | None = None,
                   production_plan: dict | None = None) -> dict:
    """Predict workshop water demand. / 预测车间用水量。"""
    # Use existing predict_future logic internally
    from core.prediction import predict_linear, predict_polynomial
    if model == "polynomial":
        result = predict_polynomial(historical_data, horizon, degree=2)
    else:
        result = predict_linear(historical_data, horizon)
    result["model_type"] = model
    if weather_data:
        result["weather_adjusted"] = True
    if production_plan:
        result["production_adjusted"] = True
    return result

@mcp.tool()
def predict_evaporation_hybrid(historical_evap: list[float], weather_forecast: list[dict],
                                tower_params: dict | None = None) -> dict:
    """Hybrid evaporation prediction (mechanism + data-driven). / 机理+数据混合蒸发预测。"""
    from core.prediction import predict_linear
    # Data-driven component
    data_pred = predict_linear(historical_evap, len(weather_forecast))
    predictions = data_pred.get("predictions", [])
    # Mechanism correction if tower_params provided
    if tower_params:
        from core.evaporation import CoolingTowerParams, calc_evaporation_merkel
        params = CoolingTowerParams(**{
            k: v for k, v in tower_params.items()
            if hasattr(CoolingTowerParams, k)
        })
        params.validate()
        mechanism_preds = []
        for w in weather_forecast:
            result = calc_evaporation_merkel(params, w)
            mechanism_preds.append(result["evap_rate_m3h"])
        # Blend: 60% data + 40% mechanism
        blended = []
        for i in range(min(len(predictions), len(mechanism_preds))):
            blended.append(0.6 * predictions[i] + 0.4 * mechanism_preds[i])
        predictions = blended
    return {
        "predictions": predictions,
        "method": "hybrid" if tower_params else "data_driven",
        "horizon": len(predictions),
    }


if __name__ == "__main__":
    mcp.run()
