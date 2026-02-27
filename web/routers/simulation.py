"""Simulation API router — tank simulation endpoints.
仿真 API 路由 — 水箱仿真接口。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import SimulationRequest

router = APIRouter()


@router.post("/run")
async def run_simulation(req: SimulationRequest):
    """Run tank simulation. / 运行水箱仿真。"""
    from mcp_servers.simulation_server import simulate_tank

    result = await asyncio.to_thread(
        simulate_tank,
        duration=req.duration,
        dt=req.dt,
        initial_h=req.initial_h,
        q_in_profile=req.q_in_profile,
        tank_params=req.tank_params,
        solver=req.solver,
    )
    return result


@router.get("/defaults")
async def get_defaults():
    """Get default simulation parameters. / 获取默认仿真参数。"""
    from core.config import get_default_simulation_params, get_default_tank_params

    return {
        "tank_params": get_default_tank_params(),
        "simulation_params": get_default_simulation_params(),
    }
