"""RateLimiter — token-bucket rate limiting for agent requests.
限流器 — 基于令牌桶的 Agent 请求限流。

Provides:
- TokenBucketLimiter: Per-agent token bucket with configurable rate/capacity
- AgentRateLimiterRegistry: Manages per-agent rate limiters
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TokenBucketLimiter:
    """Token-bucket rate limiter for a single agent.
    单个 Agent 的令牌桶限流器。

    Attributes:
        agent_id: Agent this limiter applies to
        rate: Tokens added per second
        capacity: Maximum tokens in the bucket
        tokens: Current tokens available
    """

    agent_id: str
    rate: float = 10.0       # tokens per second
    capacity: float = 20.0   # max burst
    tokens: float = 0.0
    _last_refill: float = field(default_factory=time.time)
    _total_allowed: int = 0
    _total_rejected: int = 0

    def __post_init__(self) -> None:
        if self.tokens == 0.0:
            self.tokens = self.capacity

    def _refill(self) -> None:
        """Add tokens based on elapsed time. / 根据经过时间补充令牌。"""
        now = time.time()
        elapsed = now - self._last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self._last_refill = now

    def allow(self, cost: float = 1.0) -> bool:
        """Check if a request is allowed (consumes tokens if yes).
        检查请求是否被允许（如果允许则消耗令牌）。
        """
        self._refill()
        if self.tokens >= cost:
            self.tokens -= cost
            self._total_allowed += 1
            return True
        self._total_rejected += 1
        return False

    def wait_time(self, cost: float = 1.0) -> float:
        """Calculate how long to wait before tokens are available.
        计算需要等待多久才有足够的令牌。
        """
        self._refill()
        if self.tokens >= cost:
            return 0.0
        deficit = cost - self.tokens
        return deficit / self.rate

    def to_dict(self) -> dict:
        self._refill()
        return {
            "agent_id": self.agent_id,
            "rate": self.rate,
            "capacity": self.capacity,
            "tokens_available": round(self.tokens, 2),
            "total_allowed": self._total_allowed,
            "total_rejected": self._total_rejected,
        }


class AgentRateLimiterRegistry:
    """Manages per-agent rate limiters.
    管理每个 Agent 的限流器。
    """

    def __init__(self, default_rate: float = 10.0, default_capacity: float = 20.0):
        self._limiters: dict[str, TokenBucketLimiter] = {}
        self._default_rate = default_rate
        self._default_capacity = default_capacity

    def get_limiter(self, agent_id: str) -> TokenBucketLimiter:
        """Get or create a rate limiter for an agent.
        获取或创建 Agent 的限流器。
        """
        if agent_id not in self._limiters:
            self._limiters[agent_id] = TokenBucketLimiter(
                agent_id=agent_id,
                rate=self._default_rate,
                capacity=self._default_capacity,
            )
        return self._limiters[agent_id]

    def allow(self, agent_id: str, cost: float = 1.0) -> bool:
        """Check if a request to this agent is allowed.
        检查对该 Agent 的请求是否被允许。
        """
        return self.get_limiter(agent_id).allow(cost)

    def configure(self, agent_id: str, rate: float, capacity: float) -> None:
        """Configure rate limit for an agent.
        配置 Agent 的限流参数。
        """
        limiter = self.get_limiter(agent_id)
        limiter.rate = rate
        limiter.capacity = capacity
        logger.info(
            "RateLimiter[%s]: configured rate=%.1f/s capacity=%.1f",
            agent_id, rate, capacity,
        )

    def get_all_status(self) -> dict[str, dict]:
        """Get status of all rate limiters. / 获取所有限流器状态。"""
        return {aid: lim.to_dict() for aid, lim in self._limiters.items()}
