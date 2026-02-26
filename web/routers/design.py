"""Design API router — sensitivity analysis and sizing.
设计 API 路由 — 敏感性分析与尺寸优化。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import SensitivityRequest, SizingRequest

router = APIRouter()


@router.post("/sensitivity")
async def run_sensitivity_endpoint(req: SensitivityRequest):
    """Run sensitivity analysis. / 运行敏感性分析。"""
    from mcp_servers.design_server import run_sensitivity

    result = await asyncio.to_thread(
        run_sensitivity,
        base_params=req.base_params,
        param_ranges=req.param_ranges,
        method=req.method,
        n_levels=req.n_levels,
    )
    return result


@router.post("/sizing")
async def size_tank(req: SizingRequest):
    """Compute tank sizing. / 计算水箱尺寸。"""
    from mcp_servers.design_server import optimize_design

    result = await asyncio.to_thread(
        optimize_design,
        requirements={
            "peak_demand": req.demand_peak,
            "min_reserve_time": req.duration_hours * 3600,
            "safety_factor": req.safety_factor,
        },
    )
    return result
