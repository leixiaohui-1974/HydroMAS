"""Gateway API router — unified entry point for external callers (OpenClaw/HydroClaw).
统一网关路由 — 外部调用者 (OpenClaw/HydroClaw) 的统一入口。

v2 升级：
  - 认知 API 分类 (感知/认知/决策/控制)
  - RBAC 权限校验
  - 会话管理 (多用户隔离)
  - 交互日志记录 (自进化数据源)
  - 心跳检查集成
  - 五种角色 (operator/designer/researcher/admin/teacher)
"""

from __future__ import annotations

import logging
import re
import time

from fastapi import APIRouter

from web.deps import (
    get_agent_registry,
    get_health_monitor,
    get_intent_classifier,
    get_orchestrator,
    get_skill_registry,
)
from web.models import GatewayRequest, GatewayToolRequest

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Role → capability mapping (expanded to 5 roles with cognitive categories)
# ---------------------------------------------------------------------------

ROLE_PROFILES = {
    "researcher": {
        "name": "科研助理",
        "name_en": "Research Assistant",
        "description": "仿真建模、数据分析、预测评价、知识问答",
        "cognitive_category": "cognition",
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
        "cognitive_category": "decision",
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
        "cognitive_category": "control",
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
    "admin": {
        "name": "管理员",
        "name_en": "Administrator",
        "description": "全功能访问，系统配置与管理，自进化管控",
        "cognitive_category": "all",
        "capabilities": [
            "forecast", "warning", "rehearsal", "plan",
            "four_prediction_loop", "odd_check", "global_dispatch",
            "daily_report", "leak_diagnosis", "water_balance",
            "simulation", "prediction", "evaluation", "data_analysis",
            "identification", "design", "sensitivity", "wnal_assessment",
            "full_lifecycle", "report_generation",
            "control_design", "optimization", "control_system_design",
            "optimization_design", "evap_optimization", "reuse_scheduling",
            "collaborative_dev", "content_pipeline",
        ],
        "quick_actions": [
            {"label": "系统状态", "message": "查看系统整体运行状态", "action": "system_health"},
            {"label": "心跳检查", "message": "运行全部心跳检查", "action": "heartbeat_all"},
            {"label": "自进化报告", "message": "生成自进化分析报告", "action": "evolution_report"},
            {"label": "用户统计", "message": "查看用户交互统计", "action": "interaction_stats"},
        ],
    },
    "teacher": {
        "name": "教学助理",
        "name_en": "Teaching Assistant",
        "description": "教学场景、原理演示、实验指导、受控仿真",
        "cognitive_category": "cognition",
        "capabilities": [
            "simulation", "prediction", "evaluation", "data_analysis",
            "identification", "control_system_design", "optimization_design",
            "full_lifecycle", "odd_assessment", "forecast_skill",
            "warning_skill", "rehearsal_skill",
        ],
        "quick_actions": [
            {"label": "仿真演示", "message": "演示双容水箱仿真", "action": "simulate_tank"},
            {"label": "PID整定", "message": "演示PID控制器整定过程", "action": "control_system_design"},
            {"label": "阶跃响应", "message": "分析系统阶跃响应特性", "action": "simulation"},
            {"label": "参数辨识", "message": "演示系统参数辨识", "action": "identification"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Cognitive API category mapping
# ---------------------------------------------------------------------------

COGNITIVE_CATEGORIES = {
    "perception": {
        "name_cn": "感知",
        "description": "数字孪生状态、传感器数据、异常检测",
        "skills": ["forecast_skill", "water_balance", "leak_diagnosis"],
        "apis": ["/api/simulation", "/api/water-balance", "/api/leak-detection", "/api/evaporation"],
    },
    "cognition": {
        "name_cn": "认知",
        "description": "ODD判定、四预推理、RAG知识问答、模式识别",
        "skills": ["warning_skill", "four_prediction_loop", "odd_assessment",
                   "daily_report", "data_analysis_predict"],
        "apis": ["/api/odd", "/api/prediction", "/api/evaluation"],
    },
    "decision": {
        "name_cn": "决策",
        "description": "调度优化、方案比选、RL策略、多Agent协商",
        "skills": ["rehearsal_skill", "plan_skill", "global_dispatch",
                   "reuse_scheduling", "evap_optimization", "optimization_design"],
        "apis": ["/api/scheduling", "/api/dispatch", "/api/reuse", "/api/design"],
    },
    "control": {
        "name_cn": "控制",
        "description": "PID/MPC控制、MRC应急、阀门/泵指令",
        "skills": ["control_system_design"],
        "apis": ["/api/control"],
    },
}


# ---------------------------------------------------------------------------
# HydroClaw singleton accessors (lazy)
# ---------------------------------------------------------------------------

def _get_rbac():
    if not hasattr(_get_rbac, "_instance"):
        from hydroclaw.rbac import RBACManager
        _get_rbac._instance = RBACManager()
    return _get_rbac._instance


def _get_session_mgr():
    if not hasattr(_get_session_mgr, "_instance"):
        from hydroclaw.session import SessionManager
        _get_session_mgr._instance = SessionManager()
    return _get_session_mgr._instance


def _get_interaction_logger():
    if not hasattr(_get_interaction_logger, "_instance"):
        from hydroclaw.evolution.logger import InteractionLogger
        _get_interaction_logger._instance = InteractionLogger()
    return _get_interaction_logger._instance


def _get_memory_mgr():
    if not hasattr(_get_memory_mgr, "_instance"):
        from hydroclaw.memory import MemoryManager
        _get_memory_mgr._instance = MemoryManager()
    return _get_memory_mgr._instance


def _get_personality_mgr():
    if not hasattr(_get_personality_mgr, "_instance"):
        from hydroclaw.personality import PersonalityManager
        _get_personality_mgr._instance = PersonalityManager()
    return _get_personality_mgr._instance


def _get_heartbeat():
    if not hasattr(_get_heartbeat, "_instance"):
        from hydroclaw.heartbeat import HeartbeatService
        _get_heartbeat._instance = HeartbeatService()
    return _get_heartbeat._instance


def _get_evolution_analyzer():
    if not hasattr(_get_evolution_analyzer, "_instance"):
        from hydroclaw.evolution.analyzer import EvolutionAnalyzer
        _get_evolution_analyzer._instance = EvolutionAnalyzer()
    return _get_evolution_analyzer._instance


# ---------------------------------------------------------------------------
# Gateway endpoints
# ---------------------------------------------------------------------------


@router.post("/chat")
async def gateway_chat(req: GatewayRequest):
    """Unified natural language chat endpoint for OpenClaw/HydroClaw.
    统一自然语言对话入口。

    v2: 增加 RBAC 校验、会话管理、交互日志、记忆查询。
    """
    start = time.time()
    orch = get_orchestrator()
    rbac = _get_rbac()
    session_mgr = _get_session_mgr()
    interaction_logger = _get_interaction_logger()
    memory_mgr = _get_memory_mgr()

    # Sanitize
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', req.message.strip())

    # Determine effective role (use role from request, map to RBAC role)
    effective_role = req.role if req.role in ROLE_PROFILES else "operator"

    # Session management: get or create session
    group = req.params.get("group", "default") if req.params else "default"
    channel = req.params.get("channel", "api") if req.params else "api"
    session = session_mgr.get_or_create(
        user_id=req.user_id or "anonymous",
        group=group,
        channel=channel,
        role=effective_role,
    )
    session.add_turn("user", text)

    # Intent classification
    classifier = get_intent_classifier()
    intent_result = classifier.classify(text)
    domain, domain_conf = classifier.classify_domain(text)

    # RBAC check: verify role has access to the identified skill
    skill_allowed = True
    if intent_result.target:
        skill_allowed = rbac.check_skill(effective_role, intent_result.target)
        if not skill_allowed:
            # Check if read access is available
            skill_allowed = rbac.check_skill_read(effective_role, intent_result.target)

    # Memory context: search for relevant past interactions
    memory_context = ""
    try:
        memory_results = memory_mgr.search(group, text, max_results=3)
        if memory_results:
            memory_context = "\n".join(r.content[:200] for r in memory_results[:2])
    except Exception:
        pass  # Memory search is best-effort

    # Route through orchestrator
    error_msg = ""
    try:
        if not skill_allowed:
            result = {
                "status": "denied",
                "message": f"角色 '{effective_role}' 无权执行此操作",
                "allowed_skills": rbac.get_allowed_skills(effective_role),
            }
        else:
            result = await orch.handle_request(text, req.params or {})
    except Exception:
        logger.exception("Gateway chat error")
        error_msg = "Internal error. Please try again."
        result = {"status": "error", "error": error_msg}

    elapsed = time.time() - start
    elapsed_ms = round(elapsed * 1000, 1)

    # Record in session history
    result_summary = ""
    if isinstance(result, dict):
        result_summary = result.get("summary", str(result)[:100])
    session.add_turn("assistant", result_summary or str(result)[:200])

    # Log interaction for self-evolution
    interaction_logger.log_chat(
        message=text,
        user_id=req.user_id or "",
        group=group,
        channel=channel,
        role=effective_role,
        intent_type=intent_result.route_type,
        intent_target=intent_result.target,
        intent_confidence=intent_result.confidence,
        skill_used=intent_result.target if skill_allowed else "",
        success=not error_msg and skill_allowed,
        response_time_ms=elapsed_ms,
        error=error_msg,
        result_summary=result_summary,
    )

    # Append to daily memory note
    try:
        memory_mgr.append_daily_note(
            group=group,
            content=f"Q: {text[:100]}\nA: {result_summary[:100]}",
            user_id=req.user_id or "",
        )
    except Exception:
        pass  # Daily note is best-effort

    return {
        "status": "success" if not error_msg and skill_allowed else (
            "denied" if not skill_allowed else "error"
        ),
        "result": result,
        "intent": {
            "route_type": intent_result.route_type,
            "target": intent_result.target,
            "confidence": intent_result.confidence,
            "domain": domain,
        },
        "role": effective_role,
        "user_id": req.user_id,
        "elapsed_ms": elapsed_ms,
        "session_id": req.session_id or session.session_id,
        "memory_context": memory_context[:300] if memory_context else None,
    }


@router.post("/skill")
async def gateway_skill(req: GatewayToolRequest):
    """Execute a named skill directly with RBAC check.
    直接执行指定技能（带权限校验）。
    """
    start = time.time()
    skill_reg = get_skill_registry()
    rbac = _get_rbac()
    interaction_logger = _get_interaction_logger()

    effective_role = req.role if req.role in ROLE_PROFILES else "operator"

    # RBAC check
    if not rbac.check_skill(effective_role, req.skill_name):
        return {
            "status": "denied",
            "error": f"角色 '{effective_role}' 无权执行技能 '{req.skill_name}'",
            "allowed_skills": rbac.get_allowed_skills(effective_role),
        }

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

    error_msg = ""
    try:
        result = await instance.run(req.params or {})
        response = {
            "status": "success",
            "skill": req.skill_name,
            "result": result.to_dict() if hasattr(result, "to_dict") else result,
            "elapsed_ms": round((time.time() - start) * 1000, 1),
        }
    except Exception as exc:
        logger.exception("Gateway skill error: %s", exc)
        error_msg = str(exc)
        response = {"status": "error", "skill": req.skill_name, "error": error_msg}

    # Log interaction
    interaction_logger.log_chat(
        message=f"skill:{req.skill_name}",
        role=effective_role,
        skill_used=req.skill_name,
        success=not error_msg,
        response_time_ms=round((time.time() - start) * 1000, 1),
        error=error_msg,
    )

    return response


@router.get("/roles")
async def gateway_roles():
    """Get available assistant roles and their capabilities.
    获取可用助理角色及其能力（含 RBAC 权限信息）。
    """
    rbac = _get_rbac()
    roles_with_permissions = {}
    for role_name, profile in ROLE_PROFILES.items():
        role_info = dict(profile)
        role_summary = rbac.get_role_summary(role_name)
        role_info["permissions"] = role_summary
        roles_with_permissions[role_name] = role_info

    return {
        "roles": roles_with_permissions,
        "default_role": "operator",
        "total_roles": len(ROLE_PROFILES),
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
    """List available skills, optionally filtered by role with RBAC.
    列出可用技能（带 RBAC 权限过滤）。
    """
    skill_reg = get_skill_registry()
    rbac = _get_rbac()
    skills = []
    role_caps = set()
    if role and role in ROLE_PROFILES:
        role_caps = set(ROLE_PROFILES[role]["capabilities"])

    for name, entry in skill_reg.items():
        meta = entry.get("metadata")
        if role_caps and name not in role_caps:
            continue

        # Add RBAC permission info
        permission = "execute"
        if role:
            if rbac.check_skill(role, name):
                permission = "execute"
            elif rbac.check_skill_read(role, name):
                permission = "read"
            else:
                permission = "denied"

        skills.append({
            "name": name,
            "description": meta.description if meta else "",
            "trigger_phrases": meta.trigger_phrases if meta else [],
            "has_instance": entry.get("instance") is not None,
            "permission": permission,
        })

    return {"skills": skills, "total": len(skills), "role_filter": role}


@router.get("/health")
async def gateway_health():
    """Health check for external callers (with heartbeat integration).
    外部调用者健康检查（集成心跳服务）。
    """
    monitor = get_health_monitor()
    registry = get_agent_registry()
    heartbeat = _get_heartbeat()

    heartbeat_status = heartbeat.get_status_summary()

    return {
        "status": "healthy",
        "agents_registered": len(registry.get_all_agents()),
        "platform": {
            "name": "HydroClaw",
            "version": "0.2.0",
            "layers": ["L0_core", "L1_compute", "L2_mcp", "L3_skills", "L4_agents"],
        },
        "heartbeat": heartbeat_status,
    }


# ---------------------------------------------------------------------------
# Cognitive API categories
# ---------------------------------------------------------------------------


@router.get("/cognitive")
async def gateway_cognitive_categories():
    """Get cognitive API categories (perception/cognition/decision/control).
    获取认知 API 分类。
    """
    return {
        "categories": COGNITIVE_CATEGORIES,
        "mapping": "CHS 认知闭环: 感知→认知→决策→控制",
    }


@router.get("/cognitive/{category}")
async def gateway_cognitive_detail(category: str):
    """Get details of a cognitive category.
    获取认知分类详情。
    """
    cat = COGNITIVE_CATEGORIES.get(category)
    if not cat:
        return {
            "error": f"Unknown category: {category}",
            "available": list(COGNITIVE_CATEGORIES.keys()),
        }
    return {"category": category, **cat}


# ---------------------------------------------------------------------------
# Session management endpoints
# ---------------------------------------------------------------------------


@router.get("/sessions")
async def gateway_sessions(group: str | None = None):
    """List active sessions.
    列出活跃会话。
    """
    session_mgr = _get_session_mgr()
    sessions = session_mgr.get_active_sessions(group=group)
    return {
        "sessions": [s.to_dict() for s in sessions[:50]],
        "total": session_mgr.get_session_count(),
        "scope": session_mgr.scope,
    }


# ---------------------------------------------------------------------------
# Heartbeat endpoints
# ---------------------------------------------------------------------------


@router.post("/heartbeat/run")
async def gateway_heartbeat_run(check_name: str | None = None):
    """Run heartbeat checks (all due or specific).
    运行心跳检查。
    """
    heartbeat = _get_heartbeat()
    if check_name:
        result = await heartbeat.run_check(check_name)
        return {"results": [result.to_dict()]}
    else:
        results = await heartbeat.run_all_due()
        return {"results": [r.to_dict() for r in results]}


@router.get("/heartbeat/status")
async def gateway_heartbeat_status():
    """Get heartbeat status summary.
    获取心跳状态摘要。
    """
    heartbeat = _get_heartbeat()
    return heartbeat.get_status_summary()


# ---------------------------------------------------------------------------
# Evolution / self-improvement endpoints
# ---------------------------------------------------------------------------


@router.get("/evolution/stats")
async def gateway_evolution_stats(date: str | None = None):
    """Get interaction statistics for self-evolution.
    获取交互统计（自进化数据）。
    """
    interaction_logger = _get_interaction_logger()
    return interaction_logger.get_stats(date=date)


@router.get("/evolution/report")
async def gateway_evolution_report(days: int = 7):
    """Generate self-evolution analysis report.
    生成自进化分析报告。
    """
    analyzer = _get_evolution_analyzer()
    report = analyzer.analyze(days_back=days)
    return report.to_dict()


# ---------------------------------------------------------------------------
# Memory endpoints
# ---------------------------------------------------------------------------


@router.get("/memory")
async def gateway_memory(group: str = "default"):
    """Get long-term memory for a group.
    获取群组长期记忆。
    """
    memory_mgr = _get_memory_mgr()
    return {
        "group": group,
        "memory": memory_mgr.get_memory(group),
        "daily_dates": memory_mgr.list_daily_notes(group, limit=10),
    }


@router.get("/memory/search")
async def gateway_memory_search(query: str, group: str = "default", limit: int = 5):
    """Search memory and daily notes.
    搜索记忆和每日笔记。
    """
    memory_mgr = _get_memory_mgr()
    results = memory_mgr.search(group, query, max_results=limit)
    return {
        "query": query,
        "group": group,
        "results": [
            {"content": r.content[:300], "source": r.source, "relevance": round(r.relevance, 3)}
            for r in results
        ],
        "total": len(results),
    }


# ---------------------------------------------------------------------------
# Personality endpoints
# ---------------------------------------------------------------------------


@router.get("/personality")
async def gateway_personality(group: str = "default", role: str = "operator"):
    """Get personality profile for a group/role.
    获取群组/角色的人格配置。
    """
    personality_mgr = _get_personality_mgr()
    profile = personality_mgr.load_profile(group=group, role=role)
    return {
        "group": group,
        "role": role,
        "agent_name": profile.agent_name,
        "agent_emoji": profile.agent_emoji,
        "available_groups": personality_mgr.get_all_groups(),
    }


# ---------------------------------------------------------------------------
# Report history
# ---------------------------------------------------------------------------

_REPORT_HISTORY_PATH = "/home/admin/hydromas/data/report_history.jsonl"


@router.get("/reports")
async def gateway_reports(user_id: str | None = None, limit: int = 20):
    """Get report history, optionally filtered by user_id.
    获取报告历史记录，可按用户 ID 过滤。
    """
    import json as _json
    from pathlib import Path

    history_path = Path(_REPORT_HISTORY_PATH)
    if not history_path.exists():
        return {"reports": [], "total": 0}

    records = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        if user_id and rec.get("user_id") != user_id:
            continue
        records.append(rec)

    records.reverse()  # newest first
    records = records[:limit]
    return {"reports": records, "total": len(records)}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def gateway_dashboard():
    """System status dashboard data (enhanced with HydroClaw components).
    系统状态仪表盘数据（增强 HydroClaw 组件信息）。
    """
    import json as _json
    from pathlib import Path

    registry = get_agent_registry()
    skill_reg = get_skill_registry()
    heartbeat = _get_heartbeat()
    session_mgr = _get_session_mgr()
    interaction_logger = _get_interaction_logger()

    # Recent reports
    recent_reports = []
    history_path = Path(_REPORT_HISTORY_PATH)
    if history_path.exists():
        lines = history_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines[-10:]):
            line = line.strip()
            if line:
                try:
                    recent_reports.append(_json.loads(line))
                except _json.JSONDecodeError:
                    pass

    # Unique users
    unique_users = set()
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rec = _json.loads(line)
                    uid = rec.get("user_id", "")
                    if uid:
                        unique_users.add(uid)
                except _json.JSONDecodeError:
                    pass

    all_agents = registry.get_all_agents()

    return {
        "status": "healthy",
        "platform": "HydroClaw",
        "version": "0.2.0",
        "agents": {
            "total": len(all_agents),
            "names": [a.agent_id if hasattr(a, "agent_id") else str(a)
                      for a in all_agents],
        },
        "skills": {
            "total": len(skill_reg),
            "names": list(skill_reg.keys()),
        },
        "reports": {
            "recent": recent_reports[:5],
            "total_users": len(unique_users),
        },
        "roles": list(ROLE_PROFILES.keys()),
        "cognitive_categories": list(COGNITIVE_CATEGORIES.keys()),
        "sessions": {
            "active": session_mgr.get_session_count(),
            "scope": session_mgr.scope,
        },
        "heartbeat": heartbeat.get_status_summary().get("overall_status", "unknown"),
        "interaction_stats": interaction_logger.get_stats(),
    }
