"""Control API router — PID/MPC control endpoints.
控制 API 路由 — PID/MPC 控制接口。
"""

from __future__ import annotations

from fastapi import APIRouter

from web.models import ControlRequest

router = APIRouter()


@router.post("/run")
async def run_control(req: ControlRequest):
    """Run closed-loop control simulation. / 运行闭环控制仿真。"""
    from mcp_servers.control_server import run_controller

    result = run_controller(
        setpoint=req.setpoint,
        controller_type=req.controller_type,
        simulation_config={
            "duration": req.duration,
            "dt": req.dt,
            "initial_h": req.initial_h,
            "tank_params": req.tank_params,
        },
        params=req.params,
    )
    return result


@router.get("/defaults")
async def get_defaults():
    """Get default controller parameters. / 获取默认控制器参数。"""
    from core.config import get_default_pid_params, get_default_mpc_params

    return {
        "pid": get_default_pid_params(),
        "mpc": get_default_mpc_params(),
    }
