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
    get_agent_context, get_agent_registry, get_circuit_breakers,
    get_executor, get_health_monitor, get_message_bus,
    get_rate_limiters, get_skill_registry, get_span_recorder,
)
from web.models import (
    AgentLifecycleRequest, AgentMessageRequest, BatchAgentRequest,
    CrossDomainWorkflowRequest, ExecutionPlanRequest, SkillRequest,
)

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


# ---------- Agent Lifecycle / Agent 生命周期 ----------

@router.post("/agents/{agent_id}/lifecycle")
async def agent_lifecycle(agent_id: str, req: AgentLifecycleRequest):
    """Manage agent lifecycle (start/stop/pause/resume).
    管理 Agent 生命周期（启动/停止/暂停/恢复）。
    """
    from agents.base_agent import AgentStatus

    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)
    if agent is None:
        return {"error": f"Agent '{agent_id}' not found", "status": 404}

    action = req.action
    previous = agent.status.value

    if action == "start":
        await agent.initialize()
        agent.status = AgentStatus.IDLE
    elif action == "stop":
        await agent.shutdown()
    elif action == "pause":
        agent.status = AgentStatus.PAUSED
    elif action == "resume":
        if agent.status == AgentStatus.PAUSED:
            agent.status = AgentStatus.IDLE
        else:
            return {
                "error": f"Cannot resume: agent is in '{agent.status.value}' state, not 'paused'",
            }

    return {
        "agent_id": agent_id,
        "action": action,
        "previous_status": previous,
        "current_status": agent.status.value,
    }


@router.post("/agents/batch-lifecycle")
async def batch_agent_lifecycle(req: BatchAgentRequest):
    """Batch lifecycle operation on multiple agents.
    对多个 Agent 执行批量生命周期操作。
    """
    from agents.base_agent import AgentStatus

    registry = get_agent_registry()
    results = []

    for agent_id in req.agent_ids:
        agent = registry.get_agent(agent_id)
        if agent is None:
            results.append({"agent_id": agent_id, "error": "not found"})
            continue

        previous = agent.status.value
        try:
            if req.action == "start":
                await agent.initialize()
                agent.status = AgentStatus.IDLE
            elif req.action == "stop":
                await agent.shutdown()
            elif req.action == "pause":
                agent.status = AgentStatus.PAUSED
            elif req.action == "resume":
                if agent.status == AgentStatus.PAUSED:
                    agent.status = AgentStatus.IDLE
            results.append({
                "agent_id": agent_id,
                "previous_status": previous,
                "current_status": agent.status.value,
            })
        except Exception as exc:
            results.append({"agent_id": agent_id, "error": str(exc)})

    return {"action": req.action, "results": results}


# ---------- Cross-Domain Workflow / 跨域工作流 ----------

@router.post("/cross-domain-workflow")
async def run_cross_domain_workflow(req: CrossDomainWorkflowRequest):
    """Execute a cross-domain workflow from natural language input.
    从自然语言输入执行跨域工作流。

    Flow: NL input → PlanningAgent decomposition → DAG execution
    """
    from agents.orchestrator import OrchestratorAgent

    registry = get_agent_registry()
    bus = get_message_bus()
    monitor = get_health_monitor()

    orch = OrchestratorAgent(
        agent_id="web_orchestrator",
        registry=registry,
        health_monitor=monitor,
        message_bus=bus,
    )

    result = await orch.run_cross_domain_workflow(
        req.user_input, req.params or {},
    )
    return result


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

    skills = get_skill_registry()

    return {
        "platform": "HydroOS-Agent",
        "version": "0.1.0",
        "layers": {
            "L4_agents": {
                "total": summary["total_agents"],
                "agents": summary["agents"],
            },
            "L3_skills": {"count": len(skills)},
            "L2_mcp_servers": {"count": 13},
            "L1_compute": {"engine": "Ray"},
            "L0_core": {"submodules": 14},
        },
        "capability_map": capability_map,
        "bus_connected": summary["bus_connected"],
    }


# ---------- Skill Management / 技能管理 ----------

@router.get("/skills")
async def list_skills():
    """List all registered skills with metadata.
    列出所有已注册的 Skill 及其元数据。
    """
    skills = get_skill_registry()
    result = []
    for name, entry in skills.items():
        meta = entry["metadata"]
        info: dict = {"name": name, "has_instance": entry["instance"] is not None}
        if meta:
            info["display_name"] = meta.display_name
            info["description"] = meta.description
            info["tools_required"] = meta.tools_required
            info["max_execution_time"] = meta.max_execution_time
        result.append(info)
    return {"total_skills": len(result), "skills": result}


@router.get("/skills/{skill_name}")
async def get_skill_detail(skill_name: str):
    """Get detailed information about a specific skill.
    获取特定 Skill 的详细信息。
    """
    skills = get_skill_registry()
    entry = skills.get(skill_name)
    if entry is None:
        return {"error": f"Skill '{skill_name}' not found", "status": 404}

    meta = entry["metadata"]
    info: dict = {
        "name": skill_name,
        "has_instance": entry["instance"] is not None,
        "class": entry["instance"].__class__.__name__ if entry["instance"] else None,
    }
    if meta:
        info["display_name"] = meta.display_name
        info["description"] = meta.description
        info["trigger_phrases"] = meta.trigger_phrases
        info["input_schema"] = meta.input_schema
        info["output_schema"] = meta.output_schema
        info["tools_required"] = meta.tools_required
        info["max_execution_time"] = meta.max_execution_time
    return info


@router.post("/skills/{skill_name}/execute")
async def execute_skill(skill_name: str, req: SkillRequest):
    """Execute a specific skill with given parameters.
    使用指定参数执行特定 Skill。
    """
    skills = get_skill_registry()
    entry = skills.get(skill_name)
    if entry is None:
        return {"error": f"Skill '{skill_name}' not found", "status": 404}

    instance = entry["instance"]
    if instance is None:
        return {"error": f"Skill '{skill_name}' has no executable instance", "status": 400}

    result = await instance.run(req.params)
    return {
        "skill": skill_name,
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "execution_time": round(result.execution_time, 3),
        "steps_completed": result.steps_completed,
    }


# ---------- Dashboard / 仪表板 ----------

@router.get("/dashboard")
async def get_dashboard():
    """Aggregated platform dashboard with agents, skills, health, and recent activity.
    平台聚合仪表板 — 包含 Agent、Skill、健康状态和近期活动。
    """
    registry = get_agent_registry()
    monitor = get_health_monitor()
    bus = get_message_bus()
    executor = get_executor()
    skills = get_skill_registry()

    # Agent summary
    agent_summary = registry.summary()

    # Platform health
    platform_health = monitor.get_platform_health()

    # Recent messages
    recent_messages = bus.get_history(limit=10)

    # Execution history
    exec_history = executor.get_history()

    # Skill summary
    skill_names = list(skills.keys())

    return {
        "agents": {
            "total": agent_summary["total_agents"],
            "by_status": platform_health.get("status_distribution", {}),
            "bus_connected": agent_summary["bus_connected"],
        },
        "health": {
            "total_requests": platform_health.get("total_requests", 0),
            "total_errors": platform_health.get("total_errors", 0),
            "error_rate": platform_health.get("overall_error_rate", 0.0),
        },
        "skills": {
            "total": len(skill_names),
            "names": skill_names,
        },
        "execution": {
            "total_plans": len(exec_history),
            "recent_plans": exec_history[-5:] if exec_history else [],
        },
        "messages": {
            "recent_count": len(recent_messages),
            "recent": recent_messages,
        },
    }


# ---------- Tracing / 链路追踪 ----------

@router.get("/traces")
async def list_traces(limit: int = 20):
    """List recent traces with summary info.
    列出近期 Trace 的摘要信息。
    """
    recorder = get_span_recorder()
    traces = recorder.get_recent_traces(limit=min(limit, 100))
    return {
        "total_traces": recorder.trace_count,
        "total_spans": recorder.span_count,
        "traces": traces,
    }


@router.get("/traces/{trace_id}")
async def get_trace_detail(trace_id: str):
    """Get all spans for a specific trace.
    获取特定 Trace 的所有 Span。
    """
    recorder = get_span_recorder()
    spans = recorder.get_trace(trace_id)
    if not spans:
        return {"error": f"Trace '{trace_id}' not found", "status": 404}
    return {
        "trace_id": trace_id,
        "span_count": len(spans),
        "spans": spans,
    }


@router.get("/spans")
async def query_spans(
    agent_id: str | None = None,
    status: str | None = None,
    min_duration_ms: float = 0.0,
    limit: int = 50,
):
    """Query spans with filters.
    按条件查询 Span。
    """
    from agents.tracing import SpanStatus as SS

    recorder = get_span_recorder()
    status_filter = None
    if status:
        try:
            status_filter = SS(status)
        except ValueError:
            return {"error": f"Invalid status: {status}. Use: ok, error, unset"}

    spans = recorder.query_spans(
        agent_id=agent_id,
        status=status_filter,
        min_duration_ms=min_duration_ms,
        limit=min(limit, 200),
    )
    return {"count": len(spans), "spans": spans}


# ---------- Circuit Breakers / 断路器 ----------

@router.get("/circuit-breakers")
async def list_circuit_breakers():
    """Get status of all circuit breakers.
    获取所有断路器状态。
    """
    cb_registry = get_circuit_breakers()
    statuses = cb_registry.get_all_status()
    open_breakers = cb_registry.get_open_breakers()
    return {
        "total": len(statuses),
        "open_count": len(open_breakers),
        "open_agents": open_breakers,
        "breakers": statuses,
    }


@router.post("/circuit-breakers/{agent_id}/reset")
async def reset_circuit_breaker(agent_id: str):
    """Reset a circuit breaker for a specific agent.
    重置特定 Agent 的断路器。
    """
    cb_registry = get_circuit_breakers()
    cb_registry.reset(agent_id)
    breaker = cb_registry.get_breaker(agent_id)
    return {"agent_id": agent_id, "status": breaker.state.value, "message": "Circuit breaker reset"}


# ---------- Rate Limits / 限流 ----------

@router.get("/rate-limits")
async def list_rate_limits():
    """Get status of all rate limiters.
    获取所有限流器状态。
    """
    rl_registry = get_rate_limiters()
    statuses = rl_registry.get_all_status()
    return {"total": len(statuses), "limiters": statuses}


@router.post("/rate-limits/{agent_id}")
async def configure_rate_limit(agent_id: str, rate: float = 10.0, capacity: float = 20.0):
    """Configure rate limit for a specific agent.
    配置特定 Agent 的限流参数。
    """
    rl_registry = get_rate_limiters()
    rl_registry.configure(agent_id, rate=rate, capacity=capacity)
    limiter = rl_registry.get_limiter(agent_id)
    return {"agent_id": agent_id, "configured": limiter.to_dict()}


# ---------- Deep Health Check / 深度健康检查 ----------

@router.get("/health/deep")
async def deep_health_check():
    """Comprehensive health check including circuit breakers, rate limits, and traces.
    综合健康检查 — 包含断路器、限流器和追踪。
    """
    monitor = get_health_monitor()
    cb_registry = get_circuit_breakers()
    rl_registry = get_rate_limiters()
    recorder = get_span_recorder()

    # Agent health
    agent_health = await monitor.check_all_health()

    # Circuit breaker status
    open_breakers = cb_registry.get_open_breakers()

    # Platform health
    platform = monitor.get_platform_health()

    # Recent error spans
    error_spans = recorder.query_spans(status=None, limit=5)

    return {
        "agents": agent_health,
        "platform": platform,
        "circuit_breakers": {
            "open_count": len(open_breakers),
            "open_agents": open_breakers,
        },
        "rate_limiters": {
            "total_configured": len(rl_registry.get_all_status()),
        },
        "tracing": {
            "total_traces": recorder.trace_count,
            "total_spans": recorder.span_count,
        },
        "recent_spans": error_spans,
    }
