"""Orchestration API router — multi-agent management endpoints.
多智能体编排 API 路由 — 多 Agent 管理接口。

Provides endpoints for:
- Agent registry introspection (list, search, status)
- Agent messaging (send message to an agent)
- DAG-based execution plan management
- System architecture overview
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter

from web.deps import (
    get_agent_context, get_agent_registry, get_executor,
    get_health_monitor, get_message_bus,
)
from web.models import AgentMessageRequest, ExecutionPlanRequest

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Agent Registry / Agent 注册表 ----------

@router.get("/agents")
async def list_agents():
    """List all registered agents with status and capabilities.
    列出所有已注册 Agent 及其状态和能力。
    """
    registry = get_agent_registry()
    summary = registry.summary()
    return summary


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get details of a specific agent.
    获取特定 Agent 的详细信息。
    """
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)
    if agent is None:
        return {"error": f"Agent '{agent_id}' not found", "status": 404}
    return {
        "id": agent.agent_id,
        "type": agent.__class__.__name__,
        "status": agent.status.value,
        "capabilities": agent.get_capabilities(),
        "card": agent.get_card().to_dict() if agent.get_card() else None,
    }


@router.get("/agents/by-capability/{capability}")
async def find_by_capability(capability: str):
    """Find agents that provide a specific capability.
    按能力查找 Agent。
    """
    registry = get_agent_registry()
    agents = registry.find_by_capability(capability)
    return {
        "capability": capability,
        "agents": [
            {
                "id": a.agent_id,
                "type": a.__class__.__name__,
                "capabilities": a.get_capabilities(),
            }
            for a in agents
        ],
    }


# ---------- Agent Health / Agent 健康检查 ----------

@router.get("/health")
async def check_all_health():
    """Run health checks on all registered agents.
    对所有已注册 Agent 运行健康检查。
    """
    monitor = get_health_monitor()
    result = await monitor.check_all_health()
    return result


@router.get("/agents/{agent_id}/health")
async def check_agent_health(agent_id: str):
    """Run a health check on a specific agent.
    对特定 Agent 运行健康检查。
    """
    monitor = get_health_monitor()
    result = await monitor.check_agent_health(agent_id)
    return result


@router.get("/metrics")
async def get_platform_health():
    """Get platform-wide health summary and metrics.
    获取平台整体健康摘要与指标。
    """
    monitor = get_health_monitor()
    return monitor.get_platform_health()


# ---------- Agent Messaging / Agent 消息通信 ----------

@router.post("/agents/{agent_id}/message")
async def send_agent_message(agent_id: str, req: AgentMessageRequest):
    """Send a message to a specific agent and get the response.
    向特定 Agent 发送消息并获取响应。
    """
    from agents.message import AgentMessage, MessageType

    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)
    if agent is None:
        return {"error": f"Agent '{agent_id}' not found", "status": 404}

    message = AgentMessage(
        type=MessageType.REQUEST,
        sender="web_api",
        recipient=agent_id,
        content={"action": req.action, **req.params},
    )

    bus = get_message_bus()
    response = await bus.send(message)
    if response is None:
        return {"error": "No response received", "status": 500}
    return response.to_dict()


# ---------- DAG Execution / DAG 执行 ----------

@router.post("/execute-plan")
async def execute_plan(req: ExecutionPlanRequest):
    """Execute a multi-agent DAG execution plan.
    执行多 Agent DAG 执行计划。
    """
    from agents.executor import ExecutionPlan, ExecutionTask

    executor = get_executor()

    # Build execution plan from request
    plan = ExecutionPlan(objective=req.objective)
    for task_req in req.tasks:
        plan.add_task(ExecutionTask(
            id=task_req.task_id,
            agent_id=task_req.agent_id,
            action=task_req.action,
            params=task_req.params,
            dependencies=task_req.dependencies,
        ))

    # Validate DAG (raises ValueError on cycles)
    try:
        plan.validate()
    except ValueError as e:
        return {"error": "Plan validation failed", "validation_errors": [str(e)]}

    # Execute
    result_plan = await executor.execute(plan)

    return {
        "plan_id": result_plan.id,
        "objective": result_plan.objective,
        "status": result_plan.status.value,
        "tasks": [
            {
                "id": t.id,
                "agent_id": t.agent_id,
                "action": t.action,
                "status": t.status.value,
                "result": t.result,
                "error": t.error,
            }
            for t in result_plan.tasks
        ],
    }


# ---------- Plan Management / 计划管理 ----------

@router.get("/execution-plans")
async def list_execution_plans(limit: int = 20):
    """List recent execution plans from history.
    列出最近的执行计划历史。
    """
    executor = get_executor()
    history = executor.get_history()
    return {"plans": history[-limit:], "total": len(history)}


@router.get("/agents/{agent_id}/metrics")
async def get_agent_metrics(agent_id: str):
    """Get execution metrics for a specific agent.
    获取特定 Agent 的执行指标。
    """
    monitor = get_health_monitor()
    return monitor.get_metrics(agent_id)


@router.get("/capabilities")
async def list_capabilities():
    """List all capabilities across all agents with provider mapping.
    列出所有 Agent 的能力及其提供者映射。
    """
    registry = get_agent_registry()
    summary = registry.summary()

    capability_map: dict[str, list[dict]] = {}
    for agent_info in summary["agents"]:
        for cap in agent_info["capabilities"]:
            capability_map.setdefault(cap, []).append({
                "agent_id": agent_info["id"],
                "type": agent_info["type"],
                "status": agent_info["status"],
            })

    return {
        "total_capabilities": len(capability_map),
        "capabilities": capability_map,
    }


# ---------- Negotiation / 协商 ----------

@router.get("/negotiate/{capability}")
async def negotiate_capability(capability: str):
    """Negotiate which agent should handle a capability.
    协商哪个 Agent 应处理某项能力。
    """
    from agents.negotiation import CapabilityNegotiator

    registry = get_agent_registry()
    monitor = get_health_monitor()
    negotiator = CapabilityNegotiator(registry, health_monitor=monitor)
    result = negotiator.negotiate(capability)
    return result.to_dict()


# ---------- Message Bus / 消息总线 ----------

@router.get("/message-history")
async def get_message_history(agent_id: str | None = None, limit: int = 50):
    """Get message bus history, optionally filtered by agent.
    获取消息总线历史，可按 Agent 过滤。
    """
    bus = get_message_bus()
    history = bus.get_history(agent_id=agent_id, limit=min(limit, 200))
    return {"messages": history, "count": len(history)}


# ---------- System Architecture / 系统架构 ----------

@router.get("/architecture")
async def get_architecture():
    """Return the full platform architecture overview.
    返回平台完整架构概览。
    """
    registry = get_agent_registry()
    summary = registry.summary()

    # Build capability map
    capability_map: dict[str, list[str]] = {}
    for agent_info in summary["agents"]:
        for cap in agent_info["capabilities"]:
            capability_map.setdefault(cap, []).append(agent_info["id"])

    return {
        "platform": "HydroOS-Agent",
        "version": "0.1.0",
        "layers": {
            "L4_agents": {
                "total": summary["total_agents"],
                "agents": summary["agents"],
            },
            "L3_skills": {"count": 17},
            "L2_mcp_servers": {"count": 13},
            "L1_compute": {"engine": "Ray"},
            "L0_core": {"submodules": 14},
        },
        "capability_map": capability_map,
        "bus_connected": summary["bus_connected"],
    }
