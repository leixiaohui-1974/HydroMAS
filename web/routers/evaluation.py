"""Evaluation API router — performance metrics and WNAL.
评价 API 路由 — 性能指标与 WNAL。
"""

from __future__ import annotations

from fastapi import APIRouter

from web.models import EvaluationRequest, WNALRequest

router = APIRouter()


@router.post("/performance")
async def eval_performance(req: EvaluationRequest):
    """Evaluate prediction/control performance. / 评价性能。"""
    from mcp_servers.evaluation_server import evaluate_performance

    result = evaluate_performance(
        observed=req.observed,
        predicted=req.predicted,
        metrics=req.metrics,
        time_series=req.time_series,
        setpoint=req.setpoint,
    )
    return result


@router.post("/wnal")
async def wnal_assess(req: WNALRequest):
    """Assess Water Network Autonomy Level. / 评估水网自主运行等级。"""
    from mcp_servers.evaluation_server import assess_wnal

    result = assess_wnal(system_capabilities=req.capabilities)
    return result
