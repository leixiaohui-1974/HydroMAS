"""AdaptiveScheduler — history-based dynamic task scheduling.
自适应调度器 — 基于历史指标的动态任务调度。

Uses execution history metrics to:
- Adjust task timeout budgets per agent
- Route tasks to agents with best historical performance
- Apply dynamic retry policies based on error patterns
- Provide scheduling recommendations
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentPerformanceProfile:
    """Aggregated performance profile for an agent.
    Agent 的聚合性能画像。
    """

    agent_id: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    timeout_count: int = 0
    action_stats: dict[str, dict] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 1.0
        return self.successful_tasks / self.total_tasks

    @property
    def avg_duration_ms(self) -> float:
        if self.successful_tasks == 0:
            return 0.0
        return self.total_duration_ms / self.successful_tasks

    @property
    def p95_timeout_budget(self) -> float:
        """Estimate P95 timeout budget based on max observed latency.
        根据最大观测延迟估算 P95 超时预算。
        """
        if self.max_duration_ms == 0:
            return 30000.0  # Default 30s
        return self.max_duration_ms * 1.5

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": round(self.success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.min_duration_ms != float("inf") else 0,
            "max_duration_ms": round(self.max_duration_ms, 2),
            "timeout_count": self.timeout_count,
            "p95_timeout_budget_ms": round(self.p95_timeout_budget, 2),
            "action_stats": self.action_stats,
        }


@dataclass
class SchedulingRecommendation:
    """A scheduling recommendation for a task.
    任务的调度建议。
    """

    agent_id: str
    action: str
    recommended_timeout_sec: float
    recommended_max_retries: int
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "action": self.action,
            "recommended_timeout_sec": round(self.recommended_timeout_sec, 1),
            "recommended_max_retries": self.recommended_max_retries,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
        }


class AdaptiveScheduler:
    """History-based adaptive task scheduler.
    基于历史的自适应任务调度器。

    Tracks agent execution metrics and provides intelligent scheduling
    recommendations for timeout budgets, retry policies, and agent selection.
    """

    def __init__(self):
        self._profiles: dict[str, AgentPerformanceProfile] = {}
        self._action_agent_map: dict[str, list[str]] = defaultdict(list)

    def _ensure_profile(self, agent_id: str) -> AgentPerformanceProfile:
        if agent_id not in self._profiles:
            self._profiles[agent_id] = AgentPerformanceProfile(agent_id=agent_id)
        return self._profiles[agent_id]

    def record_execution(
        self,
        agent_id: str,
        action: str,
        duration_ms: float,
        success: bool,
        timed_out: bool = False,
    ) -> None:
        """Record a task execution result for profile building.
        记录任务执行结果以构建性能画像。
        """
        profile = self._ensure_profile(agent_id)
        profile.total_tasks += 1
        profile.last_updated = time.time()

        if success:
            profile.successful_tasks += 1
            profile.total_duration_ms += duration_ms
            profile.min_duration_ms = min(profile.min_duration_ms, duration_ms)
            profile.max_duration_ms = max(profile.max_duration_ms, duration_ms)
        else:
            profile.failed_tasks += 1
            if timed_out:
                profile.timeout_count += 1

        # Track per-action stats
        if action not in profile.action_stats:
            profile.action_stats[action] = {
                "count": 0, "successes": 0, "failures": 0, "total_ms": 0.0,
            }
        stats = profile.action_stats[action]
        stats["count"] += 1
        if success:
            stats["successes"] += 1
            stats["total_ms"] += duration_ms
        else:
            stats["failures"] += 1

        # Track which agents handle which actions
        if agent_id not in self._action_agent_map[action]:
            self._action_agent_map[action].append(agent_id)

    def recommend(self, agent_id: str, action: str) -> SchedulingRecommendation:
        """Get scheduling recommendation for a specific agent + action.
        获取特定 Agent + 动作的调度建议。
        """
        profile = self._profiles.get(agent_id)

        if profile is None or profile.total_tasks == 0:
            return SchedulingRecommendation(
                agent_id=agent_id,
                action=action,
                recommended_timeout_sec=30.0,
                recommended_max_retries=2,
                confidence=0.1,
                reason="No historical data; using defaults",
            )

        # Calculate recommended timeout
        action_stats = profile.action_stats.get(action)
        if action_stats and action_stats["successes"] > 0:
            avg_ms = action_stats["total_ms"] / action_stats["successes"]
            timeout_sec = max(5.0, (avg_ms * 3) / 1000)  # 3x avg with 5s floor
            confidence = min(1.0, action_stats["count"] / 10)
        else:
            timeout_sec = profile.p95_timeout_budget / 1000
            confidence = min(0.5, profile.total_tasks / 20)

        # Calculate recommended retries
        if profile.success_rate > 0.95:
            max_retries = 1
        elif profile.success_rate > 0.8:
            max_retries = 2
        else:
            max_retries = 3

        # Build reason
        reasons = []
        if action_stats:
            reasons.append(f"{action_stats['count']} history records for '{action}'")
        reasons.append(f"success_rate={profile.success_rate:.1%}")
        if profile.timeout_count > 0:
            reasons.append(f"{profile.timeout_count} timeouts observed")

        return SchedulingRecommendation(
            agent_id=agent_id,
            action=action,
            recommended_timeout_sec=round(timeout_sec, 1),
            recommended_max_retries=max_retries,
            confidence=round(confidence, 3),
            reason="; ".join(reasons),
        )

    def find_best_agent_for_action(self, action: str) -> str | None:
        """Find the agent with the best historical performance for an action.
        找到某个动作历史性能最优的 Agent。
        """
        candidates = self._action_agent_map.get(action, [])
        if not candidates:
            return None

        best_agent = None
        best_score = -1.0

        for agent_id in candidates:
            profile = self._profiles.get(agent_id)
            if profile is None:
                continue
            action_stats = profile.action_stats.get(action, {})
            count = action_stats.get("count", 0)
            successes = action_stats.get("successes", 0)
            if count == 0:
                continue

            success_rate = successes / count
            avg_ms = action_stats.get("total_ms", 0) / max(successes, 1)
            # Score: high success rate + low latency
            score = success_rate * 100 - avg_ms / 1000
            if score > best_score:
                best_score = score
                best_agent = agent_id

        return best_agent

    def get_profile(self, agent_id: str) -> dict:
        """Get performance profile for an agent.
        获取 Agent 的性能画像。
        """
        profile = self._profiles.get(agent_id)
        if profile is None:
            return {"agent_id": agent_id, "status": "no_data"}
        return profile.to_dict()

    def get_all_profiles(self) -> dict[str, dict]:
        """Get all performance profiles. / 获取所有性能画像。"""
        return {aid: p.to_dict() for aid, p in self._profiles.items()}

    def get_scheduling_status(self) -> dict:
        """Get overall scheduling status summary.
        获取总体调度状态摘要。
        """
        total_tasks = sum(p.total_tasks for p in self._profiles.values())
        total_success = sum(p.successful_tasks for p in self._profiles.values())
        total_timeouts = sum(p.timeout_count for p in self._profiles.values())

        return {
            "total_agents_profiled": len(self._profiles),
            "total_actions_tracked": len(self._action_agent_map),
            "total_tasks_recorded": total_tasks,
            "overall_success_rate": round(total_success / max(total_tasks, 1), 4),
            "total_timeouts": total_timeouts,
            "action_coverage": {
                action: len(agents)
                for action, agents in self._action_agent_map.items()
            },
        }
