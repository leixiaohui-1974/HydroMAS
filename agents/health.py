"""AgentHealthMonitor — health checking and metrics for agents.
Agent 健康监控 — Agent 健康检查与指标收集。

Provides:
- Per-agent health checks (ping via handle_message)
- Execution metrics: request count, error rate, avg latency
- Agent status aggregation for the platform dashboard
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from agents.base_agent import AgentStatus, BaseAgent
from agents.message import AgentMessage, MessageType
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentMetrics:
    """Per-agent execution metrics. / 单 Agent 执行指标。"""

    agent_id: str
    request_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    last_request_at: float = 0.0
    last_error_at: float = 0.0
    last_health_check_at: float = 0.0
    healthy: bool = True

    @property
    def avg_latency_ms(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.total_latency_ms / self.request_count

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "error_rate": round(self.error_rate, 4),
            "last_request_at": self.last_request_at,
            "last_error_at": self.last_error_at,
            "healthy": self.healthy,
        }


class AgentHealthMonitor:
    """Monitor agent health and collect execution metrics.
    监控 Agent 健康状态并收集执行指标。
    """

    def __init__(self, registry: AgentRegistry, health_timeout: float = 5.0):
        self.registry = registry
        self.health_timeout = health_timeout
        self._metrics: dict[str, AgentMetrics] = {}

    def _ensure_metrics(self, agent_id: str) -> AgentMetrics:
        if agent_id not in self._metrics:
            self._metrics[agent_id] = AgentMetrics(agent_id=agent_id)
        return self._metrics[agent_id]

    def record_request(self, agent_id: str, latency_ms: float, success: bool) -> None:
        """Record a request execution for an agent.
        记录 Agent 的一次请求执行。
        """
        m = self._ensure_metrics(agent_id)
        m.request_count += 1
        m.total_latency_ms += latency_ms
        m.last_request_at = time.time()
        if not success:
            m.error_count += 1
            m.last_error_at = time.time()

    async def check_agent_health(self, agent_id: str) -> dict:
        """Health-check a single agent by sending a heartbeat message.
        通过发送心跳消息对单个 Agent 进行健康检查。
        """
        agent = self.registry.get_agent(agent_id)
        if agent is None:
            return {"agent_id": agent_id, "healthy": False, "error": "Agent not found"}

        m = self._ensure_metrics(agent_id)

        # Check if agent is in an error/stopped state
        if agent.status in (AgentStatus.ERROR, AgentStatus.STOPPED):
            m.healthy = False
            return {
                "agent_id": agent_id,
                "healthy": False,
                "status": agent.status.value,
                "error": f"Agent in {agent.status.value} state",
            }

        # Send a heartbeat message and measure response time
        heartbeat = AgentMessage(
            type=MessageType.HEARTBEAT,
            sender="health_monitor",
            recipient=agent_id,
            content={"action": "health_check", "timestamp": time.time()},
        )

        start = time.time()
        try:
            response = await asyncio.wait_for(
                agent.handle_message(heartbeat),
                timeout=self.health_timeout,
            )
            latency_ms = (time.time() - start) * 1000
            m.last_health_check_at = time.time()
            m.healthy = True

            return {
                "agent_id": agent_id,
                "healthy": True,
                "status": agent.status.value,
                "latency_ms": round(latency_ms, 2),
                "capabilities": agent.get_capabilities(),
            }
        except asyncio.TimeoutError:
            m.healthy = False
            return {
                "agent_id": agent_id,
                "healthy": False,
                "error": f"Health check timed out ({self.health_timeout}s)",
                "status": agent.status.value,
            }
        except Exception as exc:
            m.healthy = False
            return {
                "agent_id": agent_id,
                "healthy": False,
                "error": str(exc),
                "status": agent.status.value,
            }

    async def check_all_health(self) -> dict:
        """Run health checks on all registered agents.
        对所有已注册 Agent 运行健康检查。
        """
        all_agents = self.registry.get_all_agents()
        results = {}
        coros = []
        for agent_id in all_agents:
            coros.append(self.check_agent_health(agent_id))

        checks = await asyncio.gather(*coros, return_exceptions=True)
        for check in checks:
            if isinstance(check, Exception):
                continue
            results[check["agent_id"]] = check

        healthy_count = sum(1 for r in results.values() if r.get("healthy"))
        return {
            "total": len(all_agents),
            "healthy": healthy_count,
            "unhealthy": len(all_agents) - healthy_count,
            "agents": results,
        }

    def get_metrics(self, agent_id: str | None = None) -> dict:
        """Get execution metrics for one or all agents.
        获取单个或所有 Agent 的执行指标。
        """
        if agent_id:
            m = self._metrics.get(agent_id)
            return m.to_dict() if m else {"agent_id": agent_id, "request_count": 0}

        return {
            aid: m.to_dict()
            for aid, m in self._metrics.items()
        }

    def get_platform_health(self) -> dict:
        """Get overall platform health summary.
        获取平台整体健康摘要。
        """
        all_agents = self.registry.get_all_agents()
        status_counts: dict[str, int] = defaultdict(int)
        for agent in all_agents.values():
            status_counts[agent.status.value] += 1

        total_requests = sum(m.request_count for m in self._metrics.values())
        total_errors = sum(m.error_count for m in self._metrics.values())

        return {
            "total_agents": len(all_agents),
            "status_distribution": dict(status_counts),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "overall_error_rate": round(total_errors / total_requests, 4) if total_requests > 0 else 0.0,
        }
