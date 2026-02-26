"""DataClean API router — outlier detection and interpolation.
数据清洗 API 路由 — 异常检测与插值。
"""

from __future__ import annotations

from fastapi import APIRouter

from web.models import OutlierDetectRequest, InterpolateRequest

router = APIRouter()


@router.post("/outliers")
async def detect_outliers_endpoint(req: OutlierDetectRequest):
    """Detect outliers in time series. / 检测时序数据异常。"""
    from mcp_servers.dataclean_server import detect_outliers

    result = detect_outliers(
        data=req.data,
        method=req.method,
        threshold=req.threshold,
    )
    return result


@router.post("/interpolate")
async def interpolate_gaps(req: InterpolateRequest):
    """Interpolate missing values. / 插值缺失值。"""
    from mcp_servers.dataclean_server import clean_timeseries

    result = clean_timeseries(
        raw_data=req.data,
        methods=[req.method],
    )
    return result
