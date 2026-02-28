"""Structured tracing — span-based distributed trace for multi-agent execution.
结构化追踪 — 基于 Span 的多 Agent 执行分布式追踪。

Provides:
- TraceContext: Propagates trace_id and parent_span_id across agent calls
- Span: A single unit of work within a trace (start/end/attributes/events)
- SpanRecorder: Collects spans and exports them for analysis
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SpanStatus(str, Enum):
    """Status of a span. / Span 的状态。"""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanEvent:
    """An event within a span (log, annotation). / Span 内的事件。"""

    name: str
    timestamp: float = field(default_factory=time.time)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "attributes": self.attributes,
        }


@dataclass
class Span:
    """A single unit of work within a distributed trace.
    分布式追踪中的单个工作单元。

    Attributes:
        trace_id: ID of the overall trace
        span_id: Unique ID of this span
        parent_span_id: ID of the parent span (None for root)
        name: Human-readable name (e.g. "executor:plan_started")
        agent_id: Agent that owns this span
        start_time: When the span started
        end_time: When the span ended
        status: OK / ERROR / UNSET
        attributes: Key-value metadata
        events: Log entries within the span
    """

    trace_id: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_span_id: str | None = None
    name: str = ""
    agent_id: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    status: SpanStatus = SpanStatus.UNSET
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    error_message: str | None = None

    @property
    def duration_ms(self) -> float:
        if self.end_time > 0:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def finish(self, status: SpanStatus = SpanStatus.OK, error: str | None = None) -> None:
        """Finish this span. / 结束此 Span。"""
        self.end_time = time.time()
        self.status = status
        if error:
            self.error_message = error
            self.status = SpanStatus.ERROR

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        """Add a log event to this span. / 向此 Span 添加日志事件。"""
        self.events.append(SpanEvent(name=name, attributes=attributes or {}))

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute. / 设置 Span 属性。"""
        self.attributes[key] = value

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "agent_id": self.agent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status.value,
            "error_message": self.error_message,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
        }


@dataclass
class TraceContext:
    """Propagation context for distributed tracing.
    分布式追踪的传播上下文。

    Carries trace_id and current span_id through agent call chains.
    """

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    span_id: str = ""
    baggage: dict[str, str] = field(default_factory=dict)

    def child_context(self, new_span_id: str) -> TraceContext:
        """Create a child context for a new span.
        为新的 Span 创建子上下文。
        """
        return TraceContext(
            trace_id=self.trace_id,
            span_id=new_span_id,
            baggage=dict(self.baggage),
        )

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "baggage": self.baggage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TraceContext:
        return cls(
            trace_id=data.get("trace_id", uuid.uuid4().hex[:16]),
            span_id=data.get("span_id", ""),
            baggage=data.get("baggage", {}),
        )


class SpanRecorder:
    """Collects and stores spans for querying and export.
    收集并存储 Span 以供查询和导出。

    Thread-safe in-memory span store with trace-based indexing.
    """

    def __init__(self, max_traces: int = 500):
        self._spans: list[Span] = []
        self._traces: dict[str, list[Span]] = {}
        self.max_traces = max_traces

    def record(self, span: Span) -> None:
        """Record a completed span. / 记录一个已完成的 Span。"""
        self._spans.append(span)
        self._traces.setdefault(span.trace_id, []).append(span)
        # Evict oldest traces if over limit
        if len(self._traces) > self.max_traces:
            oldest_trace_id = next(iter(self._traces))
            oldest_spans = self._traces.pop(oldest_trace_id)
            for s in oldest_spans:
                try:
                    self._spans.remove(s)
                except ValueError:
                    pass

    def start_span(
        self,
        name: str,
        trace_ctx: TraceContext,
        agent_id: str = "",
        attributes: dict | None = None,
    ) -> Span:
        """Create and return a new span (not yet recorded — call finish + record).
        创建并返回新的 Span（尚未记录 — 需调用 finish + record）。
        """
        span = Span(
            trace_id=trace_ctx.trace_id,
            parent_span_id=trace_ctx.span_id or None,
            name=name,
            agent_id=agent_id,
            attributes=attributes or {},
        )
        return span

    def get_trace(self, trace_id: str) -> list[dict]:
        """Get all spans for a given trace. / 获取指定 Trace 的所有 Span。"""
        spans = self._traces.get(trace_id, [])
        return [s.to_dict() for s in spans]

    def get_recent_traces(self, limit: int = 20) -> list[dict]:
        """Get recent traces with summary info.
        获取近期 Trace 的摘要信息。
        """
        trace_ids = list(self._traces.keys())[-limit:]
        result = []
        for tid in reversed(trace_ids):
            spans = self._traces[tid]
            root_spans = [s for s in spans if s.parent_span_id is None]
            root = root_spans[0] if root_spans else spans[0]
            has_error = any(s.status == SpanStatus.ERROR for s in spans)
            total_duration = sum(s.duration_ms for s in spans)
            result.append({
                "trace_id": tid,
                "root_name": root.name,
                "span_count": len(spans),
                "has_error": has_error,
                "total_duration_ms": round(total_duration, 2),
                "start_time": root.start_time,
            })
        return result

    def query_spans(
        self,
        agent_id: str | None = None,
        status: SpanStatus | None = None,
        min_duration_ms: float = 0.0,
        limit: int = 50,
    ) -> list[dict]:
        """Query spans with filters. / 按条件查询 Span。"""
        results = []
        for span in reversed(self._spans):
            if agent_id and span.agent_id != agent_id:
                continue
            if status and span.status != status:
                continue
            if span.duration_ms < min_duration_ms:
                continue
            results.append(span.to_dict())
            if len(results) >= limit:
                break
        return results

    def export_all(self) -> list[dict]:
        """Export all recorded spans. / 导出所有已记录的 Span。"""
        return [s.to_dict() for s in self._spans]

    def clear(self) -> None:
        """Clear all recorded spans. / 清空所有已记录的 Span。"""
        self._spans.clear()
        self._traces.clear()

    @property
    def span_count(self) -> int:
        return len(self._spans)

    @property
    def trace_count(self) -> int:
        return len(self._traces)
