"""Dispatch API router. / 调度优化API路由。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import GlobalDispatchRequest

router = APIRouter()


@router.post("/optimize")
async def optimize_dispatch(req: GlobalDispatchRequest):
    """Optimize global water dispatch. / 运行全局水量调度优化。"""
    from mcp_servers.scheduling_server import optimize_global_dispatch

    return await asyncio.to_thread(
        optimize_global_dispatch,
        demand_forecast=req.demand_forecast,
        supply_config=req.supply_config,
        reuse_config=req.reuse_config,
        method=req.method,
    )
