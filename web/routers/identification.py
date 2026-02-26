"""Identification API router — system identification endpoints.
系统辨识 API 路由 — 参数辨识接口。
"""

from __future__ import annotations

from fastapi import APIRouter

from web.models import IdentificationRequest, ARXRequest

router = APIRouter()


@router.post("/run")
async def identify_parameters(req: IdentificationRequest):
    """Run system identification. / 运行系统辨识。"""
    from mcp_servers.identification_server import identify_parameters

    result = identify_parameters(
        observed_h=req.observed_h,
        observed_q_out=req.observed_q_out,
        model_type=req.model_type,
        initial_guess=req.initial_guess,
    )
    return result


@router.post("/arx")
async def identify_arx(req: ARXRequest):
    """Run ARX model identification. / 运行 ARX 模型辨识。"""
    from core.identification import identify_arx

    result = identify_arx(y=req.y, u=req.u, na=req.na, nb=req.nb)
    return result
