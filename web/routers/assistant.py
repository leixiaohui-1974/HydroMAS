"""Assistant API router — AI intelligent assistant endpoint.
智能助手 API 路由 — AI 智能助手接口。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Literal

from fastapi import APIRouter

from web.models import AssistantMessage

_RoleType = Literal["operator", "engineer", "analyst", "admin"]
from web.deps import get_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

# Pre-built quick action templates for each role
QUICK_ACTIONS = {
    "operator": [
        {"label": "检查 ODD 状态", "message": "检查当前系统ODD安全状态", "icon": "shield"},
        {"label": "运行四预系统", "message": "运行四预闭环分析", "icon": "alert-triangle"},
        {"label": "查看控制状态", "message": "查看当前控制器状态", "icon": "sliders"},
        {"label": "生成运营报告", "message": "生成当前系统运营报告", "icon": "file-text"},
        {"label": "水平衡核算", "message": "执行全厂水平衡核算", "icon": "droplet"},
        {"label": "泄漏检测", "message": "执行管网泄漏检测", "icon": "alert-circle"},
        {"label": "日运营报告", "message": "生成今日运营报告", "icon": "file-text"},
    ],
    "engineer": [
        {"label": "运行仿真", "message": "运行水箱仿真模拟", "icon": "play"},
        {"label": "对比 PID/MPC", "message": "比较 PID 和 MPC 控制器", "icon": "git-branch"},
        {"label": "敏感性分析", "message": "运行参数敏感性分析", "icon": "trending-up"},
        {"label": "系统辨识", "message": "运行系统参数辨识", "icon": "crosshair"},
        {"label": "蒸发预测", "message": "预测今日冷却塔蒸发量", "icon": "cloud"},
        {"label": "回用优化", "message": "优化回用水调度方案", "icon": "refresh-cw"},
        {"label": "全局调度", "message": "运行全局水量调度优化", "icon": "settings"},
    ],
    "analyst": [
        {"label": "智能预测", "message": "对水位数据进行预测分析", "icon": "trending-up"},
        {"label": "数据清洗", "message": "清洗时序数据异常值", "icon": "filter"},
        {"label": "性能评价", "message": "评价系统性能指标", "icon": "award"},
        {"label": "WNAL 评估", "message": "评估水网自主运行等级", "icon": "layers"},
    ],
    "admin": [
        {"label": "系统总览", "message": "查看系统整体状态", "icon": "monitor"},
        {"label": "全生命周期", "message": "运行全生命周期分析", "icon": "refresh-cw"},
        {"label": "WNAL 评估", "message": "评估水网自主运行等级", "icon": "layers"},
        {"label": "查看所有技能", "message": "列出所有可用技能", "icon": "list"},
    ],
}


@router.post("/chat")
async def chat(msg: AssistantMessage):
    """Process a chat message through the Orchestrator Agent.
    通过编排 Agent 处理聊天消息。
    """
    orch = get_orchestrator()

    # Sanitize control characters from user input
    sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', msg.message)

    # Classify intent
    intent = await asyncio.to_thread(orch.classify_intent, sanitized)

    # Execute
    try:
        result = await orch.handle_request(sanitized, msg.params or {})
    except Exception:
        logger.exception("Assistant error")
        result = {"status": "error", "error": "An internal error occurred. Please try again."}

    return {
        "intent": intent,
        "result": result,
        "role": msg.role,
    }


@router.get("/quick-actions/{role}")
async def get_quick_actions(role: _RoleType):
    """Get quick action buttons for a role. / 获取角色的快捷操作。"""
    actions = QUICK_ACTIONS.get(role, QUICK_ACTIONS["admin"])
    return {"actions": actions}


@router.get("/capabilities")
async def get_capabilities():
    """List all assistant capabilities. / 列出助手全部能力。"""
    from agents.orchestrator import TOOL_KEYWORDS

    return {
        "tool_keywords": dict(TOOL_KEYWORDS),
        "supported_roles": list(QUICK_ACTIONS.keys()),
    }
