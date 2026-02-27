"""Water balance API router. / 水平衡API路由。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import WaterBalanceRequest

router = APIRouter()


@router.post("/calc")
async def calc_balance(req: WaterBalanceRequest):
    """Calculate full plant water balance. / 计算全厂水平衡。"""
    from mcp_servers.water_balance_server import calc_full_plant_balance

    return await asyncio.to_thread(
        calc_full_plant_balance,
        nodes_data=req.nodes_data,
        edges_data=req.edges_data,
    )


@router.post("/anomaly")
async def detect_anomaly(req: dict):
    """Detect water balance anomalies. / 检测水平衡异常。"""
    from mcp_servers.water_balance_server import detect_balance_anomaly

    return await asyncio.to_thread(
        detect_balance_anomaly,
        residuals=req.get("residuals", {}),
        threshold=req.get("threshold", 0.03),
    )
