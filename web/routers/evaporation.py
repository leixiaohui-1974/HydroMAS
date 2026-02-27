"""Evaporation API router. / 蒸发预测API路由。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import EvaporationRequest

router = APIRouter()


@router.post("/predict")
async def predict_evaporation(req: EvaporationRequest):
    """Predict cooling tower evaporation. / 预测冷却塔蒸发量。"""
    from mcp_servers.evaporation_server import predict_evaporation as _predict

    return await asyncio.to_thread(
        _predict,
        tower_params=req.tower_params,
        weather=req.weather,
    )
