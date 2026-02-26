"""ODD API router — safety monitoring endpoints.
ODD API 路由 — 安全监测接口。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import ODDCheckRequest, ODDSeriesRequest

router = APIRouter()


@router.post("/check")
async def check_odd_endpoint(req: ODDCheckRequest):
    """Check single state against ODD. / 检查单个状态的 ODD。"""
    from mcp_servers.odd_server import check_odd

    result = await asyncio.to_thread(
        check_odd,
        current_state=req.state,
        odd_config=req.odd_config,
    )
    return result


@router.post("/check-series")
async def check_odd_series_endpoint(req: ODDSeriesRequest):
    """Check state series against ODD. / 检查状态序列的 ODD。"""
    from mcp_servers.odd_server import check_odd

    result = await asyncio.to_thread(
        check_odd,
        current_state=req.states[0] if req.states else {},
        odd_config=req.odd_config,
        check_mode="predictive",
        forecast_series=req.states,
        time_series=req.times,
    )
    return result


@router.post("/mrc-plan")
async def get_mrc_plan_endpoint(req: ODDCheckRequest):
    """Get Minimal Risk Condition plan. / 获取最小风险条件方案。"""
    from mcp_servers.odd_server import check_odd, get_mrc_plan

    # First check ODD to find violations
    check_result = await asyncio.to_thread(
        check_odd,
        current_state=req.state,
        odd_config=req.odd_config,
    )
    violations = check_result.get("violations", [])

    result = await asyncio.to_thread(
        get_mrc_plan,
        violations=violations,
        current_state=req.state,
    )
    return result


@router.get("/specs")
async def get_odd_specs():
    """Get ODD dimension specifications. / 获取 ODD 维度规格。"""
    from core.config import load_odd_specs

    return load_odd_specs()
