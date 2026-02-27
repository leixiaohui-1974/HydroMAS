"""Identification API router — system identification endpoints.
系统辨识 API 路由 — 参数辨识接口。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import ARXRequest, IdentificationRequest

router = APIRouter()


@router.post("/run")
async def identify_parameters_endpoint(req: IdentificationRequest):
    """Run system identification. / 运行系统辨识。"""
    from mcp_servers.identification_server import identify_parameters

    result = await asyncio.to_thread(
        identify_parameters,
        observed_h=req.observed_h,
        observed_q_out=req.observed_q_out,
        model_type=req.model_type,
        initial_guess=req.initial_guess,
    )
    return result


@router.post("/arx")
async def identify_arx_endpoint(req: ARXRequest):
    """Run ARX model identification via MCP server. / 通过 MCP 服务器运行 ARX 辨识。"""
    from mcp_servers.identification_server import identify_parameters

    result = await asyncio.to_thread(
        identify_parameters,
        observed_h=req.y,
        observed_q_out=req.u,
        model_type="ARX",
        arx_config={"na": req.na, "nb": req.nb, "u": req.u},
    )
    return result
