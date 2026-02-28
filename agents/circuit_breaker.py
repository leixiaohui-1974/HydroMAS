"""CircuitBreaker — resilience pattern for preventing cascading failures.
断路器 — 防止级联故障的弹性模式。

States:
  CLOSED  → Normal operation; tracks error rate
  OPEN    → Requests short-circuited; waits for recovery_timeout
  HALF_OPEN → Allows one probe request to test recovery
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker state. / 断路器状态。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Per-agent circuit breaker with sliding window error tracking.
    基于滑动窗口错误追踪的 Agent 级断路器。

    Attributes:
        agent_id: Agent this breaker protects
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds to wait before half-open probe
        half_open_max_calls: Probe calls allowed in half-open state
        window_size: Sliding window size in seconds for error counting
    """

    agent_id: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 1
    window_size: float = 60.0

    state: CircuitState = CircuitState.CLOSED
    _failure_timestamps: list[float] = field(default_factory=list)
    _success_count: int = 0
    _failure_count: int = 0
    _last_failure_at: float = 0.0
    _opened_at: float = 0.0
    _half_open_calls: int = 0

    def allow_request(self) -> bool:
        """Check if a request should be allowed through.
        检查是否允许请求通过。
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self._opened_at
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(
                    "CircuitBreaker[%s]: OPEN → HALF_OPEN after %.1fs",
                    self.agent_id, elapsed,
                )
                return True
            return False

        # HALF_OPEN — allow limited probe calls
        if self._half_open_calls < self.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False

    def record_success(self) -> None:
        """Record a successful request. / 记录成功的请求。"""
        self._success_count += 1
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self._failure_timestamps.clear()
            logger.info("CircuitBreaker[%s]: HALF_OPEN → CLOSED (recovered)", self.agent_id)

    def record_failure(self) -> None:
        """Record a failed request. / 记录失败的请求。"""
        now = time.time()
        self._failure_count += 1
        self._last_failure_at = now
        self._failure_timestamps.append(now)

        # Clean old failures outside the window
        cutoff = now - self.window_size
        self._failure_timestamps = [t for t in self._failure_timestamps if t > cutoff]

        if self.state == CircuitState.HALF_OPEN:
            self._open()
            logger.info("CircuitBreaker[%s]: HALF_OPEN → OPEN (probe failed)", self.agent_id)
        elif self.state == CircuitState.CLOSED:
            if len(self._failure_timestamps) >= self.failure_threshold:
                self._open()
                logger.warning(
                    "CircuitBreaker[%s]: CLOSED → OPEN (%d failures in %.0fs window)",
                    self.agent_id, len(self._failure_timestamps), self.window_size,
                )

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self._opened_at = time.time()

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED.
        手动重置断路器为 CLOSED 状态。
        """
        self.state = CircuitState.CLOSED
        self._failure_timestamps.clear()
        self._half_open_calls = 0
        logger.info("CircuitBreaker[%s]: manually reset to CLOSED", self.agent_id)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "recent_failures": len(self._failure_timestamps),
            "total_successes": self._success_count,
            "total_failures": self._failure_count,
            "last_failure_at": self._last_failure_at,
            "opened_at": self._opened_at if self.state != CircuitState.CLOSED else 0.0,
        }


class CircuitBreakerRegistry:
    """Manages circuit breakers for all agents.
    管理所有 Agent 的断路器。
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._default_failure_threshold = failure_threshold
        self._default_recovery_timeout = recovery_timeout

    def get_breaker(self, agent_id: str) -> CircuitBreaker:
        """Get or create a circuit breaker for an agent.
        获取或创建 Agent 的断路器。
        """
        if agent_id not in self._breakers:
            self._breakers[agent_id] = CircuitBreaker(
                agent_id=agent_id,
                failure_threshold=self._default_failure_threshold,
                recovery_timeout=self._default_recovery_timeout,
            )
        return self._breakers[agent_id]

    def allow_request(self, agent_id: str) -> bool:
        """Check if a request to this agent is allowed.
        检查对该 Agent 的请求是否被允许。
        """
        return self.get_breaker(agent_id).allow_request()

    def record_success(self, agent_id: str) -> None:
        self.get_breaker(agent_id).record_success()

    def record_failure(self, agent_id: str) -> None:
        self.get_breaker(agent_id).record_failure()

    def reset(self, agent_id: str) -> None:
        """Reset a specific agent's circuit breaker.
        重置特定 Agent 的断路器。
        """
        self.get_breaker(agent_id).reset()

    def reset_all(self) -> None:
        """Reset all circuit breakers. / 重置所有断路器。"""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_all_status(self) -> dict[str, dict]:
        """Get status of all circuit breakers. / 获取所有断路器状态。"""
        return {aid: cb.to_dict() for aid, cb in self._breakers.items()}

    def get_open_breakers(self) -> list[str]:
        """Get agent IDs with open circuit breakers.
        获取断路器处于 OPEN 状态的 Agent ID。
        """
        return [
            aid for aid, cb in self._breakers.items()
            if cb.state == CircuitState.OPEN
        ]
