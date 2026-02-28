"""Gateway API router — unified entry point for external callers (OpenClaw).
统一网关路由 — 外部调用者 (OpenClaw) 的统一入口。

OpenClaw 通过此网关调用 HydroMAS 的全部能力：
    - 自然语言对话 (chat)
    - 技能执行 (skill)
    - 工具调用 (tool)
    - 系统查询 (query)

三种角色模式：
    - researcher (科研): 仿真建模、数据分析、论文辅助
    - designer  (设计): 控制设计、优化、敏感性分析
    - operator  (运维): 四预系统、ODD、日报、调度
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

from fastapi import APIRouter

from web.deps import (
    get_agent_registry,
    get_executor,
    get_health_monitor,
    get_intent_classifier,
    get_message_bus,
    get_orchestrator,
    get_skill_registry,
)
from web.models import GatewayRequest, GatewayToolRequest

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Role → capability mapping
# ---------------------------------------------------------------------------

ROLE_PROFILES = {
    "researcher": {
        "name": "科研助理",
        "name_en": "Research Assistant",
        "description": "仿真建模、数据分析、预测评价、知识问答",
        "capabilities": [
            "simulation", "prediction", "evaluation", "data_analysis",
            "identification", "design", "sensitivity", "wnal_assessment",
            "full_lifecycle", "report_generation",
        ],
        "quick_actions": [
            {"label": "运行仿真", "message": "运行水箱仿真模拟", "action": "simulate_tank"},
            {"label": "数据分析", "message": "分析水位时序数据", "action": "data_analysis_predict"},
            {"label": "预测评价", "message": "预测未来水位变化", "action": "forecast"},
            {"label": "系统辨识", "message": "运行系统参数辨识", "action": "identification"},
            {"label": "WNAL评估", "message": "评估水网自主运行等级", "action": "wnal_assessment"},
            {"label": "全生命周期", "message": "运行全生命周期分析", "action": "full_lifecycle"},
        ],
    },
    "designer": {
        "name": "设计助理",
        "name_en": "Design Assistant",
        "description": "控制设计、优化设计、敏感性分析、回用优化、蒸发预测",
        "capabilities": [
            "control_design", "optimization", "sensitivity", "simulation",
            "control_system_design", "optimization_design", "evap_optimization",
            "reuse_scheduling", "odd_assessment",
        ],
        "quick_actions": [
            {"label": "控制设计", "message": "设计水箱PID/MPC控制系统", "action": "control_system_design"},
            {"label": "优化设计", "message": "运行水箱优化设计", "action": "optimization_design"},
            {"label": "敏感性分析", "message": "运行参数敏感性分析", "action": "sensitivity"},
            {"label": "蒸发优化", "message": "优化冷却塔蒸发效率", "action": "evap_optimization"},
            {"label": "回用优化", "message": "优化回用水调度方案", "action": "reuse_scheduling"},
            {"label": "ODD评估", "message": "评估安全运行设计域", "action": "odd_assessment"},
        ],
    },
    "operator": {
        "name": "运维助理",
        "name_en": "Operations Assistant",
        "description": "四预系统、ODD监测、调度优化、日报生成、泄漏检测、水平衡",
        "capabilities": [
            "forecast", "warning", "rehearsal", "plan",
            "four_prediction_loop", "odd_check", "global_dispatch",
            "daily_report", "leak_diagnosis", "water_balance",
        ],
        "quick_actions": [
            {"label": "四预闭环", "message": "运行四预闭环分析", "action": "four_prediction_loop"},
            {"label": "ODD检查", "message": "检查当前系统ODD安全状态", "action": "odd_check"},
            {"label": "全局调度", "message": "运行全局水量调度优化", "action": "global_dispatch"},
            {"label": "日报", "message": "生成今日运营报告", "action": "daily_report"},
            {"label": "泄漏检测", "message": "执行管网泄漏检测", "action": "leak_diagnosis"},
            {"label": "水平衡", "message": "执行全厂水平衡核算", "action": "water_balance"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Gateway endpoints
# ---------------------------------------------------------------------------


@router.post("/chat")
async def gateway_chat(req: GatewayRequest):
    """Unified natural language chat endpoint for OpenClaw.
    OpenClaw 统一自然语言对话入口。

    Accepts user text + role, routes through intent classification
    and OrchestratorAgent, returns structured result.
    """
    start = time.time()
    orch = get_orchestrator()

    # Sanitize
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', req.message.strip())

    # Intent classification
    classifier = get_intent_classifier()
    intent_result = classifier.classify(text)
    domain, domain_conf = classifier.classify_domain(text)

    # Route through orchestrator
    try:
        result = await orch.handle_request(text, req.params or {})
    except Exception:
        logger.exception("Gateway chat error")
        result = {"status": "error", "error": "Internal error. Please try again."}

    elapsed = time.time() - start

    return {
        "status": "success" if not isinstance(result, dict) or result.get("status") != "error" else "error",
        "result": result,
        "intent": {
            "route_type": intent_result.route_type,
            "target": intent_result.target,
            "confidence": intent_result.confidence,
            "domain": domain,
        },
        "role": req.role,
        "elapsed_ms": round(elapsed * 1000, 1),
        "session_id": req.session_id,
    }


@router.post("/skill")
async def gateway_skill(req: GatewayToolRequest):
    """Execute a named skill directly.
    直接执行指定技能。
    """
    start = time.time()
    skill_reg = get_skill_registry()

    entry = skill_reg.get(req.skill_name)
    if not entry:
        return {
            "status": "error",
            "error": f"Skill '{req.skill_name}' not found",
            "available_skills": list(skill_reg.keys()),
        }

    instance = entry.get("instance")
    if not instance:
        return {"status": "error", "error": f"Skill '{req.skill_name}' has no implementation"}

    try:
        result = instance.run(req.params or {})
        return {
            "status": "success",
            "skill": req.skill_name,
            "result": result.to_dict() if hasattr(result, "to_dict") else result,
            "elapsed_ms": round((time.time() - start) * 1000, 1),
        }
    except Exception as exc:
        logger.exception("Gateway skill error: %s", exc)
        return {"status": "error", "skill": req.skill_name, "error": str(exc)}


@router.get("/roles")
async def gateway_roles():
    """Get available assistant roles and their capabilities.
    获取可用助理角色及其能力。
    """
    return {
        "roles": ROLE_PROFILES,
        "default_role": "operator",
    }


@router.get("/roles/{role}/actions")
async def gateway_role_actions(role: str):
    """Get quick actions for a specific role.
    获取角色快捷操作。
    """
    profile = ROLE_PROFILES.get(role)
    if not profile:
        return {"error": f"Unknown role: {role}", "available": list(ROLE_PROFILES.keys())}
    return {
        "role": role,
        "name": profile["name"],
        "actions": profile["quick_actions"],
    }


@router.get("/skills")
async def gateway_skills(role: str | None = None):
    """List available skills, optionally filtered by role.
    列出可用技能，可选按角色过滤。
    """
    skill_reg = get_skill_registry()
    skills = []
    role_caps = set()
    if role and role in ROLE_PROFILES:
        role_caps = set(ROLE_PROFILES[role]["capabilities"])

    for name, entry in skill_reg.items():
        meta = entry.get("metadata")
        if role_caps and name not in role_caps:
            continue
        skills.append({
            "name": name,
            "description": meta.description if meta else "",
            "trigger_phrases": meta.trigger_phrases[:3] if meta else [],
            "has_instance": entry.get("instance") is not None,
        })

    return {"skills": skills, "total": len(skills), "role_filter": role}


@router.get("/health")
async def gateway_health():
    """Health check for external callers.
    外部调用者健康检查。
    """
    monitor = get_health_monitor()
    registry = get_agent_registry()

    return {
        "status": "healthy",
        "agents_registered": len(registry.get_all_agents()),
        "platform": {
            "version": "0.1.0",
            "layers": ["L0_core", "L1_compute", "L2_mcp", "L3_skills", "L4_agents"],
        },
    }
