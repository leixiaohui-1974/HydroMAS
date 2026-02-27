"""Leak detection API router. / 泄漏检测API路由。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import LeakDetectionRequest

router = APIRouter()


@router.post("/detect")
async def detect_leak(req: LeakDetectionRequest):
    """Detect leaks in pipe network. / 检测管网泄漏。"""
    from mcp_servers.leak_detection_server import build_network_graph
    from mcp_servers.leak_detection_server import detect_leak as _detect

    graph_data = await asyncio.to_thread(
        build_network_graph,
        nodes=req.graph_nodes,
        edges=req.graph_edges,
    )
    return await asyncio.to_thread(
        _detect,
        graph_data=graph_data,
        threshold=req.threshold,
    )


@router.post("/localize")
async def localize_leak(req: dict):
    """Localize most likely leak locations. / 定位最可能的泄漏位置。"""
    from mcp_servers.leak_detection_server import localize_leak as _localize

    return await asyncio.to_thread(
        _localize,
        graph_data=req.get("graph_data", {}),
        anomaly_scores=req.get("anomaly_scores", {}),
        top_k=req.get("top_k", 3),
    )
