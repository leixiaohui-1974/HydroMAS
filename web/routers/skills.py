"""Skills API router — workflow skill execution endpoints.
技能 API 路由 — 工作流技能执行接口。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from web.models import SkillRequest, FourPredRequest

router = APIRouter()


def _sanitize_floats(obj):
    """Replace NaN/Inf with None for JSON compliance."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_floats(v) for v in obj]
    return obj


def _serialize_skill_result(result) -> dict:
    """Convert SkillResult to a JSON-serializable dict."""
    return _sanitize_floats({
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "steps_completed": result.steps_completed,
        "execution_time": result.execution_time,
    })


@router.get("/list")
async def list_skills():
    """List all available skills. / 列出所有可用技能。"""
    from agents.orchestrator import OrchestratorAgent

    orch = OrchestratorAgent()
    return {"skills": orch.get_available_skills()}


@router.post("/run")
async def run_skill(req: SkillRequest):
    """Execute a skill by name. / 按名称执行技能。"""
    from agents.orchestrator import OrchestratorAgent

    orch = OrchestratorAgent()
    available = orch.get_available_skills()
    valid_names = [s["name"] for s in available] if isinstance(available, list) else []
    if valid_names and req.skill_name not in valid_names:
        raise ValueError(
            f"Unknown skill: '{req.skill_name}'. "
            f"Available: {', '.join(valid_names)}"
        )
    result = await orch.handle_request(req.skill_name, req.params)
    return result


@router.post("/four-prediction")
async def run_four_prediction(req: FourPredRequest):
    """Run the 四预 loop (Forecast→Warning→Rehearsal→Plan).
    运行四预闭环（预报→预警→预演→预案）。
    """
    from skills.four_prediction_loop import FourPredictionLoopSkill

    skill = FourPredictionLoopSkill()
    result = await skill.run({
        "water_level_data": req.water_level_data,
        "inflow_data": req.inflow_data,
        "risk_threshold": req.risk_threshold,
    })
    return _serialize_skill_result(result)


@router.post("/lifecycle")
async def run_lifecycle(params: dict | None = None):
    """Run full lifecycle skill. / 运行全生命周期技能。"""
    from skills.full_lifecycle import FullLifecycleSkill

    skill = FullLifecycleSkill()
    result = await skill.run(params or {})
    return _serialize_skill_result(result)


@router.post("/control-design")
async def run_control_design(params: dict | None = None):
    """Run control system design skill. / 运行控制系统设计技能。"""
    from skills.control_system_design import ControlSystemDesignSkill

    skill = ControlSystemDesignSkill()
    result = await skill.run(params or {})
    return _serialize_skill_result(result)


@router.post("/report/control")
async def generate_control_report(results: dict):
    """Generate control system report. / 生成控制系统报告。"""
    from agents.report_agent import ReportAgent

    agent = ReportAgent()
    report_md = await asyncio.to_thread(agent.generate_control_report, results)
    return {"report_markdown": report_md}


@router.post("/report/odd")
async def generate_odd_report(results: dict):
    """Generate ODD assessment report. / 生成 ODD 评估报告。"""
    from agents.report_agent import ReportAgent

    agent = ReportAgent()
    report_md = await asyncio.to_thread(agent.generate_odd_report, results)
    return {"report_markdown": report_md}


@router.post("/report/lifecycle")
async def generate_lifecycle_report(results: dict):
    """Generate lifecycle report. / 生成全生命周期报告。"""
    from agents.report_agent import ReportAgent

    agent = ReportAgent()
    report_md = await asyncio.to_thread(agent.generate_lifecycle_report, results)
    return {"report_markdown": report_md}
