"""Reuse water API router. / 回用水API路由。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import ReuseRequest

router = APIRouter()


@router.post("/match")
async def match_reuse(req: ReuseRequest):
    """Match reuse water paths. / 匹配回用水路径。"""
    from mcp_servers.reuse_server import match_reuse_path

    return await asyncio.to_thread(
        match_reuse_path,
        source_quality=req.source_quality,
        target_requirements=req.target_requirements,
    )


@router.post("/optimize")
async def optimize_reuse(req: dict):
    """Optimize reuse water schedule. / 优化回用水调度方案。"""
    from mcp_servers.reuse_server import optimize_reuse_schedule

    return await asyncio.to_thread(
        optimize_reuse_schedule,
        sources=req.get("sources", []),
        demands=req.get("demands", []),
        constraints=req.get("constraints"),
    )
