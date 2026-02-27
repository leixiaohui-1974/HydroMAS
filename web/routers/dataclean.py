"""DataClean API router — outlier detection and interpolation.
数据清洗 API 路由 — 异常检测与插值。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import InterpolateRequest, OutlierDetectRequest

router = APIRouter()


@router.post("/outliers")
async def detect_outliers_endpoint(req: OutlierDetectRequest):
    """Detect outliers in time series. / 检测时序数据异常。"""
    from mcp_servers.dataclean_server import detect_outliers

    result = await asyncio.to_thread(
        detect_outliers,
        data=req.data,
        method=req.method,
        threshold=req.threshold,
    )
    return result


@router.post("/interpolate")
async def interpolate_gaps(req: InterpolateRequest):
    """Interpolate missing values. / 插值缺失值。"""
    from mcp_servers.dataclean_server import clean_timeseries

    # Map short method names to clean_timeseries pipeline names
    method_map = {
        "linear": "interpolate_linear",
        "spline": "interpolate_spline",
        "median": "median_filter",
    }
    pipeline_method = method_map.get(req.method, req.method)

    result = await asyncio.to_thread(
        clean_timeseries,
        raw_data=[v if v is not None else float("nan") for v in req.data],
        methods=[pipeline_method],
    )
    return result
