"""Tests for Phase 5 — Observability & Resilience.
Phase 5 测试 — 可观测性与弹性。

Covers:
- Structured tracing (TraceContext, Span, SpanRecorder)
- Circuit breaker (CircuitBreaker, CircuitBreakerRegistry)
- Rate limiter (TokenBucketLimiter, AgentRateLimiterRegistry)
- Executor integration (tracing + circuit breaker + rate limiter)
"""

import asyncio
import time

import pytest

from agents.base_agent import AgentStatus, BaseAgent
from agents.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, CircuitState
from agents.context import AgentContext
from agents.executor import ExecutionPlan, ExecutionTask, MultiAgentExecutor, TaskStatus
from agents.message import AgentMessage, MessageBus, MessageType
from agents.rate_limiter import AgentRateLimiterRegistry, TokenBucketLimiter
from agents.registry import AgentRegistry
from agents.tracing import Span, SpanRecorder, SpanStatus, TraceContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class EchoAgent(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["echo"]

    async def handle_message(self, msg: AgentMessage) -> AgentMessage:
        if msg.type == MessageType.HEARTBEAT:
            return msg.reply({"status": "alive"})
        return msg.reply({"echo": msg.content})


class FailAgent(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["fail"]

    async def handle_message(self, msg: AgentMessage) -> AgentMessage:
        raise RuntimeError("FailAgent always fails")


class SlowAgent(BaseAgent):
    def get_capabilities(self) -> list[str]:
        return ["slow"]

    async def handle_message(self, msg: AgentMessage) -> AgentMessage:
        await asyncio.sleep(10)
        return msg.reply({"status": "done"})


# ===========================================================================
# TraceContext tests
# ===========================================================================

class TestTraceContext:
    def test_create_trace_context(self):
        ctx = TraceContext()
        assert len(ctx.trace_id) == 16
        assert ctx.span_id == ""

    def test_child_context(self):
        ctx = TraceContext()
        ctx.baggage["user"] = "test"
        child = ctx.child_context("child-span-1")
        assert child.trace_id == ctx.trace_id
        assert child.span_id == "child-span-1"
        assert child.baggage["user"] == "test"

    def test_to_from_dict(self):
        ctx = TraceContext(trace_id="abc123", span_id="span-1")
        ctx.baggage["key"] = "val"
        d = ctx.to_dict()
        restored = TraceContext.from_dict(d)
        assert restored.trace_id == "abc123"
        assert restored.span_id == "span-1"
        assert restored.baggage["key"] == "val"


# ===========================================================================
# Span tests
# ===========================================================================

class TestSpan:
    def test_span_finish(self):
        span = Span(trace_id="t1", name="test_op")
        time.sleep(0.01)
        span.finish()
        assert span.status == SpanStatus.OK
        assert span.end_time > span.start_time
        assert span.duration_ms > 0

    def test_span_finish_with_error(self):
        span = Span(trace_id="t1", name="fail_op")
        span.finish(status=SpanStatus.ERROR, error="boom")
        assert span.status == SpanStatus.ERROR
        assert span.error_message == "boom"

    def test_span_add_event(self):
        span = Span(trace_id="t1", name="op")
        span.add_event("log_entry", {"msg": "hello"})
        assert len(span.events) == 1
        assert span.events[0].name == "log_entry"

    def test_span_set_attribute(self):
        span = Span(trace_id="t1", name="op")
        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"

    def test_span_to_dict(self):
        span = Span(trace_id="t1", name="op", agent_id="agent-1")
        span.finish()
        d = span.to_dict()
        assert d["trace_id"] == "t1"
        assert d["name"] == "op"
        assert d["agent_id"] == "agent-1"
        assert d["status"] == "ok"


# ===========================================================================
# SpanRecorder tests
# ===========================================================================

class TestSpanRecorder:
    def test_record_and_get_trace(self):
        recorder = SpanRecorder()
        span = Span(trace_id="t1", name="op1")
        span.finish()
        recorder.record(span)
        trace = recorder.get_trace("t1")
        assert len(trace) == 1
        assert trace[0]["name"] == "op1"

    def test_recent_traces(self):
        recorder = SpanRecorder()
        for i in range(5):
            span = Span(trace_id=f"t{i}", name=f"op{i}")
            span.finish()
            recorder.record(span)
        traces = recorder.get_recent_traces(limit=3)
        assert len(traces) == 3
        # Most recent first
        assert traces[0]["trace_id"] == "t4"

    def test_query_spans_by_agent(self):
        recorder = SpanRecorder()
        for aid in ["a1", "a2", "a1"]:
            span = Span(trace_id="t1", name="op", agent_id=aid)
            span.finish()
            recorder.record(span)
        results = recorder.query_spans(agent_id="a1")
        assert len(results) == 2

    def test_query_spans_by_status(self):
        recorder = SpanRecorder()
        s1 = Span(trace_id="t1", name="ok_op")
        s1.finish(status=SpanStatus.OK)
        recorder.record(s1)
        s2 = Span(trace_id="t1", name="err_op")
        s2.finish(status=SpanStatus.ERROR, error="fail")
        recorder.record(s2)
        errors = recorder.query_spans(status=SpanStatus.ERROR)
        assert len(errors) == 1
        assert errors[0]["name"] == "err_op"

    def test_start_span(self):
        recorder = SpanRecorder()
        ctx = TraceContext(trace_id="t1", span_id="parent")
        span = recorder.start_span("child_op", ctx, agent_id="a1")
        assert span.trace_id == "t1"
        assert span.parent_span_id == "parent"
        assert span.agent_id == "a1"

    def test_eviction_on_max_traces(self):
        recorder = SpanRecorder(max_traces=3)
        for i in range(5):
            span = Span(trace_id=f"t{i}", name=f"op{i}")
            span.finish()
            recorder.record(span)
        assert recorder.trace_count <= 3

    def test_export_all(self):
        recorder = SpanRecorder()
        for i in range(3):
            span = Span(trace_id="t1", name=f"op{i}")
            span.finish()
            recorder.record(span)
        exported = recorder.export_all()
        assert len(exported) == 3

    def test_clear(self):
        recorder = SpanRecorder()
        span = Span(trace_id="t1", name="op")
        span.finish()
        recorder.record(span)
        recorder.clear()
        assert recorder.span_count == 0
        assert recorder.trace_count == 0


# ===========================================================================
# CircuitBreaker tests
# ===========================================================================

class TestCircuitBreaker:
    def test_closed_allows_requests(self):
        cb = CircuitBreaker(agent_id="a1", failure_threshold=3)
        assert cb.allow_request() is True
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(agent_id="a1", failure_threshold=3, window_size=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(agent_id="a1", failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(agent_id="a1", failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.06)
        cb.allow_request()  # Transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(agent_id="a1", failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.06)
        cb.allow_request()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_manual_reset(self):
        cb = CircuitBreaker(agent_id="a1", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_to_dict(self):
        cb = CircuitBreaker(agent_id="a1")
        d = cb.to_dict()
        assert d["agent_id"] == "a1"
        assert d["state"] == "closed"

    def test_success_does_not_open(self):
        cb = CircuitBreaker(agent_id="a1", failure_threshold=3)
        cb.record_success()
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerRegistry:
    def test_get_breaker_creates_new(self):
        reg = CircuitBreakerRegistry()
        cb = reg.get_breaker("a1")
        assert cb.agent_id == "a1"

    def test_allow_and_record(self):
        reg = CircuitBreakerRegistry(failure_threshold=2)
        assert reg.allow_request("a1") is True
        reg.record_failure("a1")
        reg.record_failure("a1")
        assert reg.allow_request("a1") is False

    def test_get_open_breakers(self):
        reg = CircuitBreakerRegistry(failure_threshold=2)
        reg.record_failure("a1")
        reg.record_failure("a1")
        reg.record_success("a2")
        assert reg.get_open_breakers() == ["a1"]

    def test_reset_all(self):
        reg = CircuitBreakerRegistry(failure_threshold=1)
        reg.record_failure("a1")
        reg.record_failure("a2")
        reg.reset_all()
        assert reg.get_open_breakers() == []


# ===========================================================================
# Rate Limiter tests
# ===========================================================================

class TestTokenBucketLimiter:
    def test_allows_within_capacity(self):
        lim = TokenBucketLimiter(agent_id="a1", rate=10, capacity=5)
        for _ in range(5):
            assert lim.allow() is True
        assert lim.allow() is False  # Exhausted

    def test_refills_over_time(self):
        lim = TokenBucketLimiter(agent_id="a1", rate=100, capacity=5)
        for _ in range(5):
            lim.allow()
        time.sleep(0.06)  # ~6 tokens refilled at 100/s
        assert lim.allow() is True

    def test_wait_time(self):
        lim = TokenBucketLimiter(agent_id="a1", rate=10, capacity=1)
        lim.allow()  # Use the one token
        wt = lim.wait_time()
        assert wt > 0

    def test_to_dict(self):
        lim = TokenBucketLimiter(agent_id="a1", rate=10, capacity=20)
        d = lim.to_dict()
        assert d["agent_id"] == "a1"
        assert d["rate"] == 10.0


class TestAgentRateLimiterRegistry:
    def test_get_limiter_creates_new(self):
        reg = AgentRateLimiterRegistry()
        lim = reg.get_limiter("a1")
        assert lim.agent_id == "a1"

    def test_allow(self):
        reg = AgentRateLimiterRegistry(default_rate=100, default_capacity=3)
        assert reg.allow("a1") is True
        assert reg.allow("a1") is True
        assert reg.allow("a1") is True
        assert reg.allow("a1") is False

    def test_configure(self):
        reg = AgentRateLimiterRegistry()
        reg.configure("a1", rate=1.0, capacity=2.0)
        lim = reg.get_limiter("a1")
        assert lim.rate == 1.0
        assert lim.capacity == 2.0

    def test_get_all_status(self):
        reg = AgentRateLimiterRegistry()
        reg.allow("a1")
        reg.allow("a2")
        status = reg.get_all_status()
        assert "a1" in status
        assert "a2" in status


# ===========================================================================
# Executor integration tests
# ===========================================================================

class TestExecutorObservabilityIntegration:
    """Test executor with tracing, circuit breaker, and rate limiter."""

    def _build_executor(self, agents_map, with_tracing=True, with_cb=True, with_rl=True):
        registry = AgentRegistry()
        bus = MessageBus()
        registry.connect_bus(bus)
        for aid, agent in agents_map.items():
            registry.register(agent)
        ctx = AgentContext()
        recorder = SpanRecorder() if with_tracing else None
        cb_reg = CircuitBreakerRegistry() if with_cb else None
        rl_reg = AgentRateLimiterRegistry() if with_rl else None
        executor = MultiAgentExecutor(
            registry=registry,
            context=ctx,
            message_bus=bus,
            span_recorder=recorder,
            circuit_breakers=cb_reg,
            rate_limiters=rl_reg,
        )
        return executor, recorder, cb_reg, rl_reg

    @pytest.mark.asyncio
    async def test_tracing_records_plan_and_task_spans(self):
        echo = EchoAgent(agent_id="echo")
        executor, recorder, _, _ = self._build_executor({"echo": echo})
        plan = ExecutionPlan(objective="test-trace")
        plan.add_task(ExecutionTask(id="t1", agent_id="echo", action="test"))
        await executor.execute(plan)
        assert recorder.trace_count == 1
        assert recorder.span_count == 2  # plan span + task span

    @pytest.mark.asyncio
    async def test_tracing_error_span_on_failure(self):
        fail = FailAgent(agent_id="fail")
        executor, recorder, _, _ = self._build_executor({"fail": fail})
        plan = ExecutionPlan(objective="fail-trace")
        plan.add_task(ExecutionTask(
            id="t1", agent_id="fail", action="test", max_retries=0,
        ))
        await executor.execute(plan)
        spans = recorder.query_spans(status=SpanStatus.ERROR)
        assert len(spans) >= 1  # At least the task span should be ERROR

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_after_failures(self):
        fail = FailAgent(agent_id="fail")
        executor, _, cb_reg, _ = self._build_executor(
            {"fail": fail}, with_tracing=False, with_rl=False,
        )
        # Record enough failures to trip the breaker
        for _ in range(5):
            cb_reg.record_failure("fail")
        plan = ExecutionPlan(objective="cb-test")
        plan.add_task(ExecutionTask(id="t1", agent_id="fail", action="test"))
        result = await executor.execute(plan)
        failed = [t for t in result.tasks if t.status == TaskStatus.FAILED]
        assert len(failed) == 1
        assert "Circuit breaker" in failed[0].error

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_when_exhausted(self):
        echo = EchoAgent(agent_id="echo")
        executor, _, _, rl_reg = self._build_executor(
            {"echo": echo}, with_tracing=False, with_cb=False,
        )
        # Configure very low capacity
        rl_reg.configure("echo", rate=0.001, capacity=0)
        plan = ExecutionPlan(objective="rl-test")
        plan.add_task(ExecutionTask(id="t1", agent_id="echo", action="test"))
        result = await executor.execute(plan)
        failed = [t for t in result.tasks if t.status == TaskStatus.FAILED]
        assert len(failed) == 1
        assert "Rate limit" in failed[0].error

    @pytest.mark.asyncio
    async def test_success_records_to_circuit_breaker(self):
        echo = EchoAgent(agent_id="echo")
        executor, _, cb_reg, _ = self._build_executor(
            {"echo": echo}, with_tracing=False, with_rl=False,
        )
        plan = ExecutionPlan(objective="cb-success")
        plan.add_task(ExecutionTask(id="t1", agent_id="echo", action="test"))
        await executor.execute(plan)
        breaker = cb_reg.get_breaker("echo")
        assert breaker._success_count >= 1

    @pytest.mark.asyncio
    async def test_multi_task_creates_multiple_spans(self):
        echo = EchoAgent(agent_id="echo")
        executor, recorder, _, _ = self._build_executor({"echo": echo})
        plan = ExecutionPlan(objective="multi-span")
        plan.add_task(ExecutionTask(id="t1", agent_id="echo", action="a1"))
        plan.add_task(ExecutionTask(id="t2", agent_id="echo", action="a2"))
        plan.add_task(ExecutionTask(
            id="t3", agent_id="echo", action="a3", dependencies=["t1", "t2"],
        ))
        await executor.execute(plan)
        # 1 plan span + 3 task spans = 4
        assert recorder.span_count == 4

    @pytest.mark.asyncio
    async def test_executor_without_observability(self):
        """Executor works fine without tracing/cb/rl (backward compat)."""
        echo = EchoAgent(agent_id="echo")
        executor, _, _, _ = self._build_executor(
            {"echo": echo}, with_tracing=False, with_cb=False, with_rl=False,
        )
        plan = ExecutionPlan(objective="no-obs")
        plan.add_task(ExecutionTask(id="t1", agent_id="echo", action="test"))
        result = await executor.execute(plan)
        assert result.status == TaskStatus.COMPLETED
