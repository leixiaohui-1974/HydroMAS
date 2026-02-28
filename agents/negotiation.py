"""Agent Negotiation Protocol — capability bidding and assignment.
Agent 协商协议 — 能力竞标与分配。

When multiple agents can handle a capability, the negotiation protocol
solicits bids from candidates, scores them, and selects the best agent.

Bid scoring factors:
    - Agent health status
    - Error rate (lower is better)
    - Average latency (lower is better)
    - Agent-declared affinity score (optional)
    - Current load / status

协商流程：
    1. 能力请求 → 查找候选 Agent
    2. 候选 Agent 生成 Bid（竞标）
    3. Negotiator 评分排序
    4. 选择最优 Agent 执行
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import AgentStatus, BaseAgent
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentBid:
    """A bid from an agent for a capability request.
    Agent 对能力请求的竞标。

    Attributes:
        agent_id: Bidding agent's identifier
        capability: The capability being bid on
        affinity: Agent-declared affinity score (0.0-1.0, higher = more suited)
        load_factor: Current load factor (0.0=idle, 1.0=fully loaded)
        metadata: Additional bid metadata
    """

    agent_id: str
    capability: str
    affinity: float = 0.5
    load_factor: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class NegotiationResult:
    """Result of a capability negotiation.
    能力协商结果。

    Attributes:
        capability: The requested capability
        winner: The selected agent (or None)
        bids: All bids received, sorted by score
        scores: Score for each bid
        reason: Human-readable reason for selection
    """

    capability: str
    winner: BaseAgent | None = None
    bids: list[AgentBid] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "capability": self.capability,
            "winner": self.winner.agent_id if self.winner else None,
            "bids": [
                {
                    "agent_id": b.agent_id,
                    "affinity": b.affinity,
                    "load_factor": b.load_factor,
                    "score": self.scores.get(b.agent_id, 0.0),
                }
                for b in self.bids
            ],
            "reason": self.reason,
        }


class CapabilityNegotiator:
    """Negotiation engine for multi-agent capability assignment.
    多 Agent 能力分配的协商引擎。

    Phase 6 enhancements:
        - History-based preference learning (winner tracking per capability)
        - Multi-round negotiation support
        - Adaptive weight adjustment based on negotiation outcomes

    Usage:
        negotiator = CapabilityNegotiator(registry, health_monitor)
        result = negotiator.negotiate("water_balance_analysis")
        if result.winner:
            # Use result.winner to handle the task
    """

    def __init__(
        self,
        registry: AgentRegistry,
        health_monitor: Any | None = None,
    ):
        self.registry = registry
        self.health_monitor = health_monitor

        # Scoring weights (configurable)
        self.weight_health: float = 0.3
        self.weight_error_rate: float = 0.25
        self.weight_latency: float = 0.20
        self.weight_affinity: float = 0.15
        self.weight_load: float = 0.10

        # Phase 6: History-based preference learning
        self._negotiation_history: list[dict] = []
        self._winner_counts: dict[str, dict[str, int]] = {}  # capability → {agent_id: count}
        self._max_history = 200

    def negotiate(self, capability: str) -> NegotiationResult:
        """Negotiate and select the best agent for a capability.
        协商并选择能力的最佳 Agent。

        Steps:
            1. Find candidate agents
            2. Collect bids (auto-generated from agent metrics)
            3. Score each bid
            4. Select winner

        Args:
            capability: The capability to negotiate for

        Returns:
            NegotiationResult with winner and scoring details.
        """
        result = NegotiationResult(capability=capability)

        # Step 1: Find candidates
        candidates = self.registry.find_by_capability(capability)
        if not candidates:
            result.reason = f"No agents provide capability '{capability}'"
            return result

        if len(candidates) == 1:
            result.winner = candidates[0]
            result.reason = "Single candidate — no negotiation needed"
            bid = self._generate_bid(candidates[0], capability)
            result.bids = [bid]
            result.scores = {bid.agent_id: 1.0}
            return result

        # Step 2: Collect bids from all candidates
        for agent in candidates:
            bid = self._generate_bid(agent, capability)
            result.bids.append(bid)

        # Step 3: Score each bid
        for bid in result.bids:
            score = self._score_bid(bid)
            result.scores[bid.agent_id] = round(score, 4)

        # Step 4: Select winner (highest score)
        result.bids.sort(key=lambda b: result.scores.get(b.agent_id, 0), reverse=True)
        best_bid = result.bids[0]
        best_agent = self.registry.get_agent(best_bid.agent_id)

        if best_agent:
            result.winner = best_agent
            runner_up = result.bids[1].agent_id if len(result.bids) > 1 else "none"
            result.reason = (
                f"Selected {best_bid.agent_id} (score={result.scores[best_bid.agent_id]:.3f}) "
                f"over {runner_up} from {len(result.bids)} candidates"
            )

        logger.info(
            "Negotiation for '%s': winner=%s (%d candidates)",
            capability,
            result.winner.agent_id if result.winner else "none",
            len(result.bids),
        )

        # Record negotiation history
        self._record_negotiation(capability, result)

        return result

    def _generate_bid(self, agent: BaseAgent, capability: str) -> AgentBid:
        """Auto-generate a bid for an agent based on its state and metrics.
        根据 Agent 状态和指标自动生成竞标。
        """
        # Determine load factor from agent status
        load_map = {
            AgentStatus.IDLE: 0.0,
            AgentStatus.RUNNING: 0.5,
            AgentStatus.ERROR: 0.9,
            AgentStatus.STOPPED: 1.0,
        }
        load = load_map.get(agent.status, 0.5)

        # Determine affinity (all capabilities equally weighted for now)
        affinity = 0.5

        return AgentBid(
            agent_id=agent.agent_id,
            capability=capability,
            affinity=affinity,
            load_factor=load,
            metadata={
                "status": agent.status.value,
                "type": agent.__class__.__name__,
            },
        )

    # ------------------------------------------------------------------
    # History-based preference learning (Phase 6)
    # ------------------------------------------------------------------

    def _record_negotiation(self, capability: str, result: NegotiationResult) -> None:
        """Record negotiation outcome for preference learning.
        记录协商结果以供偏好学习。
        """
        entry = {
            "timestamp": time.time(),
            "capability": capability,
            "winner": result.winner.agent_id if result.winner else None,
            "candidates": len(result.bids),
            "scores": dict(result.scores),
        }
        self._negotiation_history.append(entry)
        if len(self._negotiation_history) > self._max_history:
            self._negotiation_history = self._negotiation_history[-self._max_history:]

        # Update winner counts
        if result.winner:
            if capability not in self._winner_counts:
                self._winner_counts[capability] = {}
            counts = self._winner_counts[capability]
            counts[result.winner.agent_id] = counts.get(result.winner.agent_id, 0) + 1

    def get_preference(self, capability: str) -> dict:
        """Get historical winner preference for a capability.
        获取某能力的历史赢家偏好。
        """
        counts = self._winner_counts.get(capability, {})
        total = sum(counts.values())
        if total == 0:
            return {"capability": capability, "preferences": {}, "total": 0}
        prefs = {aid: round(c / total, 3) for aid, c in sorted(
            counts.items(), key=lambda x: x[1], reverse=True,
        )}
        return {
            "capability": capability,
            "preferences": prefs,
            "total": total,
            "top_agent": max(counts, key=counts.get) if counts else None,
        }

    def get_negotiation_history(self, limit: int = 20) -> list[dict]:
        """Get recent negotiation history.
        获取近期协商历史。
        """
        return list(reversed(self._negotiation_history[-limit:]))

    def get_all_preferences(self) -> dict[str, dict]:
        """Get preferences for all negotiated capabilities.
        获取所有已协商能力的偏好。
        """
        return {cap: self.get_preference(cap) for cap in self._winner_counts}

    def _score_bid(self, bid: AgentBid) -> float:
        """Score a bid using weighted multi-criteria evaluation.
        使用加权多标准评估对竞标评分。

        Score = w1 * health + w2 * (1 - error_rate) + w3 * (1 - norm_latency)
                + w4 * affinity + w5 * (1 - load_factor)

        All components are normalized to [0, 1].
        """
        # Health component (from health monitor metrics)
        health_score = 1.0
        error_rate_score = 1.0
        latency_score = 1.0

        if self.health_monitor:
            m = self.health_monitor.get_metrics(bid.agent_id)
            health_score = 1.0 if m.get("healthy", True) else 0.0
            error_rate_score = 1.0 - min(m.get("error_rate", 0.0), 1.0)
            # Normalize latency: 0ms = 1.0, 1000ms+ = 0.0
            avg_latency = m.get("avg_latency_ms", 0.0)
            latency_score = max(0.0, 1.0 - avg_latency / 1000.0)

        # Affinity and load
        affinity_score = bid.affinity
        load_score = 1.0 - bid.load_factor

        # Weighted sum
        score = (
            self.weight_health * health_score
            + self.weight_error_rate * error_rate_score
            + self.weight_latency * latency_score
            + self.weight_affinity * affinity_score
            + self.weight_load * load_score
        )
        return score
