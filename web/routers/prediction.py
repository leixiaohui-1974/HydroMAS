"""Prediction API router — forecasting endpoints.
预测 API 路由 — 预报接口。
"""

from __future__ import annotations

from fastapi import APIRouter

from web.models import PredictionRequest

router = APIRouter()


@router.post("/run")
async def run_prediction(req: PredictionRequest):
    """Run prediction model. / 运行预测模型。"""
    from mcp_servers.prediction_server import predict_future

    result = predict_future(
        historical_data=req.historical_data,
        horizon=req.horizon,
        model=req.model,
        lookback=req.lookback,
        degree=req.degree,
    )
    return result


@router.get("/sample-data")
async def get_sample_data():
    """Load sample time series data. / 加载示例时序数据。"""
    import math
    from core.config import load_sample_timeseries

    data = load_sample_timeseries()
    # Sanitize non-JSON-compliant floats (inf, nan)
    for key in data:
        data[key] = [0.0 if (math.isnan(v) or math.isinf(v)) else v for v in data[key]]
    return data
