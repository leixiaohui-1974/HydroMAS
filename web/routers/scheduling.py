"""Scheduling API router — optimization endpoints.
调度 API 路由 — 优化接口。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import SchedulingRequest

router = APIRouter()


@router.post("/run")
async def run_scheduling(req: SchedulingRequest):
    """Run schedule optimization. / 运行调度优化。"""
    from mcp_servers.scheduling_server import optimize_schedule

    result = await asyncio.to_thread(
        optimize_schedule,
        demand_forecast=req.demand_forecast,
        supply_capacity=req.supply_capacity or 0.05,
        constraints=req.constraints,
        objective=req.objective,
        method=req.method,
    )
    return result
