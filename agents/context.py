"""AgentContext — shared blackboard for multi-agent collaboration.
AgentContext — 多 Agent 协作的共享黑板。

Provides a structured shared state (blackboard pattern) that agents
can read from and write to during collaborative workflows. Includes
execution trace logging for audit and debugging.
"""

from __future__ import annotations

import copy
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trace entry for audit logging
# ---------------------------------------------------------------------------

@dataclass
class TraceEntry:
    """A single entry in the execution trace.
    执行跟踪中的单个条目。
    """

    agent_id: str
    action: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "action": self.action,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# AgentContext — shared blackboard
# ---------------------------------------------------------------------------

class AgentContext:
    """Shared context / blackboard for multi-agent collaboration.
    多 Agent 协作的共享上下文 / 黑板。

    Features:
        - Key-value shared state (blackboard pattern)
        - Namespaced sections for agent-specific data
        - Execution trace for audit and debugging
        - Deep-copy isolation to prevent accidental mutation
    """

    def __init__(self, context_id: str | None = None):
        self.context_id: str = context_id or uuid.uuid4().hex[:12]
        self._state: dict[str, Any] = {}
        self._trace: list[TraceEntry] = []
        self._created_at: float = time.time()

    # ------------------------------------------------------------------
    # Shared state (blackboard)
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the shared state (returns deep copy).
        从共享状态获取值（返回深拷贝）。
        """
        value = self._state.get(key, default)
        try:
            return copy.deepcopy(value)
        except Exception:
            return value

    def set(self, key: str, value: Any, agent_id: str = "") -> None:
        """Set a value in the shared state.
        在共享状态中设置值。
        """
        self._state[key] = value
        if agent_id:
            self._trace.append(TraceEntry(
                agent_id=agent_id,
                action=f"set:{key}",
                data={"key": key},
            ))

    def update(self, data: dict[str, Any], agent_id: str = "") -> None:
        """Update multiple values in the shared state.
        批量更新共享状态中的值。
        """
        self._state.update(data)
        if agent_id:
            self._trace.append(TraceEntry(
                agent_id=agent_id,
                action="update",
                data={"keys": list(data.keys())},
            ))

    def delete(self, key: str, agent_id: str = "") -> None:
        """Delete a key from the shared state. / 删除共享状态中的键。"""
        self._state.pop(key, None)
        if agent_id:
            self._trace.append(TraceEntry(
                agent_id=agent_id,
                action=f"delete:{key}",
            ))

    def has(self, key: str) -> bool:
        """Check if a key exists. / 检查键是否存在。"""
        return key in self._state

    def keys(self) -> list[str]:
        """List all keys in the shared state. / 列出共享状态中的所有键。"""
        return list(self._state.keys())

    # ------------------------------------------------------------------
    # Namespaced sections (per-agent isolated state)
    # ------------------------------------------------------------------

    def get_section(self, namespace: str) -> dict[str, Any]:
        """Get the state section for a specific namespace (agent).
        获取特定命名空间（Agent）的状态区段。
        """
        section = self._state.get(f"_ns:{namespace}", {})
        try:
            return copy.deepcopy(section)
        except Exception:
            return section

    def set_section(self, namespace: str, data: dict[str, Any], agent_id: str = "") -> None:
        """Set the state section for a namespace.
        设置命名空间的状态区段。
        """
        self._state[f"_ns:{namespace}"] = data
        if agent_id:
            self._trace.append(TraceEntry(
                agent_id=agent_id,
                action=f"set_section:{namespace}",
                data={"keys": list(data.keys())},
            ))

    def update_section(self, namespace: str, data: dict[str, Any], agent_id: str = "") -> None:
        """Merge data into a namespace section.
        将数据合并到命名空间区段。
        """
        key = f"_ns:{namespace}"
        if key not in self._state:
            self._state[key] = {}
        self._state[key].update(data)
        if agent_id:
            self._trace.append(TraceEntry(
                agent_id=agent_id,
                action=f"update_section:{namespace}",
                data={"keys": list(data.keys())},
            ))

    # ------------------------------------------------------------------
    # Execution trace
    # ------------------------------------------------------------------

    def add_trace(self, agent_id: str, action: str, data: dict | None = None) -> None:
        """Add a trace entry for audit logging.
        添加审计日志跟踪条目。
        """
        self._trace.append(TraceEntry(
            agent_id=agent_id,
            action=action,
            data=data or {},
        ))

    def get_trace(self, agent_id: str | None = None, limit: int = 50) -> list[dict]:
        """Get execution trace, optionally filtered by agent.
        获取执行跟踪，可按 Agent 过滤。
        """
        entries = self._trace
        if agent_id:
            entries = [e for e in entries if e.agent_id == agent_id]
        return [e.to_dict() for e in entries[-limit:]]

    # ------------------------------------------------------------------
    # Snapshot / serialization
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Create a snapshot of the entire context state.
        创建整个上下文状态的快照。
        """
        return {
            "context_id": self.context_id,
            "created_at": self._created_at,
            "state_keys": list(self._state.keys()),
            "trace_count": len(self._trace),
            "state": copy.deepcopy(self._state),
        }

    def clear(self) -> None:
        """Clear all state and trace. / 清空所有状态和跟踪。"""
        self._state.clear()
        self._trace.clear()

    def __repr__(self) -> str:
        return (
            f"<AgentContext id={self.context_id} "
            f"keys={len(self._state)} traces={len(self._trace)}>"
        )
