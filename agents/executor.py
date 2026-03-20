"""MultiAgentExecutor — DAG-based collaborative task execution engine.
MultiAgentExecutor — 基于 DAG 的多 Agent 协作任务执行引擎。

Executes task graphs across multiple agents with dependency tracking,
parallel execution of independent tasks, error handling, and retry logic.
Integrates with the MessageBus, AgentRegistry, and AgentContext.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.base_agent import AgentStatus, BaseAgent
from agents.context import AgentContext
from agents.message import AgentMessage, MessageType
from agents.registry import AgentRegistry
from agents.tracing import SpanRecorder, SpanStatus, TraceContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task node for execution DAG
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Status of a task in the execution DAG. / 执行 DAG 中任务的状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionTask:
    """A task node in the multi-agent execution DAG.
    多 Agent 执行 DAG 中的任务节点。

    Attributes:
        id: Unique task identifier
        agent_id: Target agent to execute this task
        action: Action name / type for the agent
        params: Parameters to pass to the agent
        dependencies: IDs of tasks that must complete first
        status: Current task status
        result: Task execution result
        error: Error message if failed
        started_at: Start timestamp
        completed_at: Completion timestamp
        retries: Number of retry attempts
        max_retries: Maximum retry attempts allowed
    """

    id: str
    agent_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: float = 0.0
    completed_at: float = 0.0
    retries: int = 0
    max_retries: int = 2
    timeout_sec: float = 30.0
    priority: int = 1  # 0=low, 1=normal, 2=high, 3=critical
    cancelled: bool = False

    @property
    def duration(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "action": self.action,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "duration": round(self.duration, 3),
            "retries": self.retries,
            "timeout_sec": self.timeout_sec,
            "priority": self.priority,
            "cancelled": self.cancelled,
        }


# ---------------------------------------------------------------------------
# Execution plan (DAG of tasks)
# ---------------------------------------------------------------------------

@dataclass
class ExecutionPlan:
    """A directed acyclic graph of tasks to execute across agents.
    跨 Agent 执行的任务有向无环图。
    """

    id: str = field(default_factory=lambda: f"PLAN-{uuid.uuid4().hex[:8]}")
    objective: str = ""
    tasks: list[ExecutionTask] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def add_task(self, task: ExecutionTask) -> None:
        self.tasks.append(task)

    def validate(self) -> None:
        """Validate the DAG has no cycles. / 验证 DAG 无环。"""
        task_ids = {t.id for t in self.tasks}
        adj: dict[str, list[str]] = {t.id: list(t.dependencies) for t in self.tasks}
        visited: set[str] = set()
        in_stack: set[str] = set()

        for tid, deps in adj.items():
            missing = [dep for dep in deps if dep not in task_ids]
            if missing:
                missing_list = ", ".join(sorted(missing))
                raise ValueError(f"Task '{tid}' has unknown dependencies: {missing_list}")

        def _dfs(tid: str) -> None:
            if tid in in_stack:
                raise ValueError(f"Cycle detected involving task '{tid}'")
            if tid in visited:
                return
            in_stack.add(tid)
            for dep in adj.get(tid, []):
                _dfs(dep)
            in_stack.discard(tid)
            visited.add(tid)

        for t in self.tasks:
            _dfs(t.id)

    def get_ready_tasks(self) -> list[ExecutionTask]:
        """Get tasks whose dependencies are all completed.
        获取依赖已全部完成的任务。
        """
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING
            and all(d in completed_ids for d in t.dependencies)
        ]

    def get_failed_tasks(self) -> list[ExecutionTask]:
        """Get all failed tasks. / 获取所有失败的任务。"""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]

    @property
    def all_completed(self) -> bool:
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
            for t in self.tasks
        )

    @property
    def has_failures(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "objective": self.objective,
            "status": self.status.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# MultiAgentExecutor
# ---------------------------------------------------------------------------

class MultiAgentExecutor:
    """DAG-based multi-agent task execution engine.
    基于 DAG 的多 Agent 任务执行引擎。

    Features:
        - Topological execution respecting dependencies
        - Parallel execution of independent tasks
        - Retry logic for transient failures
        - Integration with AgentRegistry, MessageBus, and AgentContext
        - Execution trace for audit
    """

    def __init__(
        self,
        registry: AgentRegistry,
        context: AgentContext | None = None,
        health_monitor: Any | None = None,
        message_bus: Any | None = None,
        span_recorder: SpanRecorder | None = None,
        circuit_breakers: Any | None = None,
        rate_limiters: Any | None = None,
    ):
        self.registry = registry
        self.context = context or AgentContext()
        self.health_monitor = health_monitor
        self.message_bus = message_bus
        self.span_recorder = span_recorder
        self.circuit_breakers = circuit_breakers
        self.rate_limiters = rate_limiters
        self._execution_history: list[ExecutionPlan] = []

    async def execute(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Execute a plan by running tasks in topological order.
        按拓扑顺序执行计划中的任务。

        Independent tasks are run concurrently via asyncio.gather.

        Args:
            plan: The execution plan (DAG) to execute

        Returns:
            The updated ExecutionPlan with results.
        """
        plan.validate()
        plan.status = TaskStatus.RUNNING
        self.context.set("current_plan_id", plan.id, agent_id="executor")
        self.context.add_trace("executor", "plan_started", {"plan_id": plan.id})

        logger.info("Executor: starting plan %s with %d tasks", plan.id, len(plan.tasks))

        # Create trace context for this plan execution
        trace_ctx = TraceContext()
        trace_ctx.baggage["plan_id"] = plan.id

        # Start plan-level span
        plan_span = None
        if self.span_recorder:
            plan_span = self.span_recorder.start_span(
                name=f"plan:{plan.objective or plan.id}",
                trace_ctx=trace_ctx,
                agent_id="executor",
                attributes={"plan_id": plan.id, "task_count": len(plan.tasks)},
            )
            trace_ctx = trace_ctx.child_context(plan_span.span_id)

        # Emit plan_started event
        await self._emit_event("plan.started", {
            "plan_id": plan.id, "objective": plan.objective,
            "task_count": len(plan.tasks),
        })

        while True:
            ready = plan.get_ready_tasks()
            if not ready:
                break

            # Sort by priority (higher first) for deterministic ordering
            ready.sort(key=lambda t: t.priority, reverse=True)

            # Execute all ready tasks concurrently
            coros = [self._execute_task(task, plan, trace_ctx) for task in ready]
            await asyncio.gather(*coros)

            # Check for unrecoverable failures
            if plan.has_failures:
                # Check if remaining tasks depend on failed ones
                failed_ids = {t.id for t in plan.get_failed_tasks()}
                remaining = [
                    t for t in plan.tasks
                    if t.status == TaskStatus.PENDING
                ]
                all_blocked = all(
                    any(d in failed_ids for d in t.dependencies)
                    for t in remaining
                ) if remaining else True

                if all_blocked and remaining:
                    logger.warning(
                        "Executor: all remaining tasks blocked by failures in plan %s",
                        plan.id,
                    )
                    for t in remaining:
                        t.status = TaskStatus.SKIPPED
                    break

        plan.completed_at = time.time()
        plan.status = (
            TaskStatus.COMPLETED if plan.all_completed and not plan.has_failures
            else TaskStatus.FAILED
        )

        self.context.set("plan_result", plan.to_dict(), agent_id="executor")
        self.context.add_trace("executor", "plan_completed", {
            "plan_id": plan.id,
            "status": plan.status.value,
            "duration": plan.completed_at - plan.created_at,
        })
        self._execution_history.append(plan)

        # Finish plan-level span
        if plan_span and self.span_recorder:
            plan_span.set_attribute("status", plan.status.value)
            plan_span.set_attribute("duration", plan.completed_at - plan.created_at)
            plan_span.finish(
                status=SpanStatus.OK if not plan.has_failures else SpanStatus.ERROR,
                error="Plan has failed tasks" if plan.has_failures else None,
            )
            self.span_recorder.record(plan_span)

        # Emit plan_completed event
        await self._emit_event("plan.completed", {
            "plan_id": plan.id, "status": plan.status.value,
            "duration": plan.completed_at - plan.created_at,
        })

        logger.info(
            "Executor: plan %s %s (%.2fs)",
            plan.id, plan.status.value,
            plan.completed_at - plan.created_at,
        )
        return plan

    async def _execute_task(
        self,
        task: ExecutionTask,
        plan: ExecutionPlan,
        trace_ctx: TraceContext | None = None,
    ) -> None:
        """Execute a single task by sending a message to the target agent.
        通过向目标 Agent 发送消息来执行单个任务。

        Supports timeout, cancellation, circuit breaker, and rate limiting.
        """
        # Check cancellation before starting
        if task.cancelled:
            task.status = TaskStatus.SKIPPED
            task.error = "Task cancelled before execution"
            task.completed_at = time.time()
            return

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        agent = self.registry.get_agent(task.agent_id)
        if agent is None:
            # Try finding best agent by capability (health-aware)
            agent = self.registry.find_best_agent(
                task.action, health_monitor=self.health_monitor,
            )
            if agent is None:
                task.status = TaskStatus.FAILED
                task.error = f"No agent found for '{task.agent_id}' or capability '{task.action}'"
                task.completed_at = time.time()
                logger.error("Executor: %s", task.error)
                return

        # Circuit breaker check
        if self.circuit_breakers and not self.circuit_breakers.allow_request(agent.agent_id):
            task.status = TaskStatus.FAILED
            task.error = f"Circuit breaker OPEN for agent '{agent.agent_id}'"
            task.completed_at = time.time()
            logger.warning("Executor: %s", task.error)
            return

        # Rate limiter check
        if self.rate_limiters and not self.rate_limiters.allow(agent.agent_id):
            task.status = TaskStatus.FAILED
            task.error = f"Rate limit exceeded for agent '{agent.agent_id}'"
            task.completed_at = time.time()
            logger.warning("Executor: %s", task.error)
            return

        # Start task-level span
        task_span = None
        if self.span_recorder and trace_ctx:
            task_span = self.span_recorder.start_span(
                name=f"task:{task.action}",
                trace_ctx=trace_ctx,
                agent_id=agent.agent_id,
                attributes={"task_id": task.id, "plan_id": plan.id, "action": task.action},
            )

        # Collect dependency results into task params
        dep_results = {}
        for dep_id in task.dependencies:
            dep_task = next((t for t in plan.tasks if t.id == dep_id), None)
            if dep_task and dep_task.result:
                dep_results[dep_id] = dep_task.result
        if dep_results:
            task.params["_dependency_results"] = dep_results

        # Build message
        message = AgentMessage(
            type=MessageType.REQUEST,
            sender="executor",
            recipient=agent.agent_id,
            content={
                "action": task.action,
                "params": task.params,
                "task_id": task.id,
                "plan_id": plan.id,
            },
        )

        # Execute with retry + timeout
        for attempt in range(task.max_retries + 1):
            # Check cancellation between retries
            if task.cancelled:
                task.status = TaskStatus.SKIPPED
                task.error = "Task cancelled during execution"
                task.completed_at = time.time()
                agent.status = AgentStatus.IDLE
                return

            try:
                agent.status = AgentStatus.RUNNING
                response = await asyncio.wait_for(
                    agent.handle_message(message),
                    timeout=task.timeout_sec,
                )
                agent.status = AgentStatus.IDLE

                if response.type == MessageType.ERROR:
                    raise RuntimeError(response.content.get("error", "Unknown error"))

                task.result = response.content
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()

                # Store result in context
                self.context.set(
                    f"task:{task.id}:result",
                    task.result,
                    agent_id=agent.agent_id,
                )
                self.context.add_trace(agent.agent_id, f"task_completed:{task.id}", {
                    "action": task.action,
                    "duration": task.duration,
                })

                # Record success in health monitor + circuit breaker
                if self.health_monitor:
                    self.health_monitor.record_request(
                        agent.agent_id, task.duration * 1000, success=True,
                    )
                if self.circuit_breakers:
                    self.circuit_breakers.record_success(agent.agent_id)

                # Finish task span
                if task_span and self.span_recorder:
                    task_span.finish(status=SpanStatus.OK)
                    self.span_recorder.record(task_span)

                # Emit task_completed event
                await self._emit_event("task.completed", {
                    "task_id": task.id, "agent_id": agent.agent_id,
                    "action": task.action, "duration": task.duration,
                })

                logger.info(
                    "Executor: task %s completed by %s (%.2fs)",
                    task.id, agent.agent_id, task.duration,
                )
                return

            except asyncio.TimeoutError:
                task.retries = attempt + 1
                agent.status = AgentStatus.IDLE
                if attempt < task.max_retries:
                    logger.warning(
                        "Executor: task %s timed out (%.1fs) — retrying (%d/%d)",
                        task.id, task.timeout_sec, attempt + 1, task.max_retries,
                    )
                    await asyncio.sleep(0.1 * (attempt + 1))
                else:
                    task.status = TaskStatus.FAILED
                    task.error = f"Task timed out after {task.timeout_sec}s ({task.retries} attempts)"
                    task.completed_at = time.time()
                    if self.health_monitor:
                        self.health_monitor.record_request(
                            agent.agent_id, task.timeout_sec * 1000, success=False,
                        )
                    if self.circuit_breakers:
                        self.circuit_breakers.record_failure(agent.agent_id)
                    if task_span and self.span_recorder:
                        task_span.finish(status=SpanStatus.ERROR, error=task.error)
                        self.span_recorder.record(task_span)
                    self.context.add_trace(agent.agent_id, f"task_timeout:{task.id}", {
                        "timeout_sec": task.timeout_sec,
                        "retries": task.retries,
                    })
                    logger.error("Executor: task %s timed out", task.id)

            except Exception as exc:
                task.retries = attempt + 1
                if attempt < task.max_retries:
                    logger.warning(
                        "Executor: task %s attempt %d failed: %s — retrying",
                        task.id, attempt + 1, exc,
                    )
                    await asyncio.sleep(0.1 * (attempt + 1))
                else:
                    task.status = TaskStatus.FAILED
                    task.error = str(exc)
                    task.completed_at = time.time()
                    agent.status = AgentStatus.IDLE
                    if self.health_monitor:
                        latency = (task.completed_at - task.started_at) * 1000
                        self.health_monitor.record_request(
                            agent.agent_id, latency, success=False,
                        )
                    if self.circuit_breakers:
                        self.circuit_breakers.record_failure(agent.agent_id)
                    if task_span and self.span_recorder:
                        task_span.finish(status=SpanStatus.ERROR, error=str(exc))
                        self.span_recorder.record(task_span)
                    self.context.add_trace(agent.agent_id, f"task_failed:{task.id}", {
                        "error": str(exc),
                        "retries": task.retries,
                    })
                    logger.error(
                        "Executor: task %s failed after %d attempts: %s",
                        task.id, task.retries, exc,
                    )

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    async def _emit_event(self, topic: str, data: dict) -> None:
        """Publish a domain event via MessageBus if connected.
        通过 MessageBus 发布领域事件（如已连接）。
        """
        if self.message_bus is None:
            return
        event = AgentMessage(
            type=MessageType.EVENT,
            sender="executor",
            content={"topic": topic, **data},
        )
        try:
            await self.message_bus.publish(topic, event)
        except Exception as exc:
            logger.debug("Executor: event publish failed for %s: %s", topic, exc)

    # ------------------------------------------------------------------
    # Plan cancellation
    # ------------------------------------------------------------------

    def cancel_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Cancel all pending tasks in a plan.
        取消计划中所有待执行的任务。
        """
        for task in plan.tasks:
            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.cancelled = True
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.SKIPPED
                    task.error = "Cancelled by user"
                    task.completed_at = time.time()
        plan.status = TaskStatus.FAILED
        plan.completed_at = time.time()
        self.context.add_trace("executor", "plan_cancelled", {"plan_id": plan.id})
        logger.info("Executor: plan %s cancelled", plan.id)
        return plan

    # ------------------------------------------------------------------
    # Plan builders
    # ------------------------------------------------------------------

    def build_sequential_plan(
        self,
        objective: str,
        steps: list[dict],
    ) -> ExecutionPlan:
        """Build a sequential (linear chain) execution plan.
        构建顺序（线性链）执行计划。

        Args:
            objective: Plan objective description
            steps: List of dicts with keys: agent_id, action, params

        Returns:
            ExecutionPlan with chained tasks.
        """
        plan = ExecutionPlan(objective=objective)
        prev_id = ""
        for i, step in enumerate(steps):
            task = ExecutionTask(
                id=f"step_{i+1}",
                agent_id=step["agent_id"],
                action=step["action"],
                params=step.get("params", {}),
                dependencies=[prev_id] if prev_id else [],
            )
            plan.add_task(task)
            prev_id = task.id
        return plan

    def build_parallel_plan(
        self,
        objective: str,
        tasks: list[dict],
    ) -> ExecutionPlan:
        """Build a plan where all tasks run in parallel (no dependencies).
        构建所有任务并行运行的计划（无依赖）。
        """
        plan = ExecutionPlan(objective=objective)
        for i, task_def in enumerate(tasks):
            task = ExecutionTask(
                id=f"parallel_{i+1}",
                agent_id=task_def["agent_id"],
                action=task_def["action"],
                params=task_def.get("params", {}),
            )
            plan.add_task(task)
        return plan

    def build_fan_out_fan_in_plan(
        self,
        objective: str,
        parallel_tasks: list[dict],
        aggregator: dict,
    ) -> ExecutionPlan:
        """Build a fan-out/fan-in plan: parallel tasks → aggregator.
        构建扇出/扇入计划：并行任务 → 聚合器。

        Args:
            objective: Plan objective
            parallel_tasks: Tasks to run concurrently
            aggregator: Final task that depends on all parallel tasks
        """
        plan = ExecutionPlan(objective=objective)
        parallel_ids: list[str] = []

        for i, task_def in enumerate(parallel_tasks):
            task = ExecutionTask(
                id=f"fan_{i+1}",
                agent_id=task_def["agent_id"],
                action=task_def["action"],
                params=task_def.get("params", {}),
            )
            plan.add_task(task)
            parallel_ids.append(task.id)

        agg_task = ExecutionTask(
            id="aggregator",
            agent_id=aggregator["agent_id"],
            action=aggregator["action"],
            params=aggregator.get("params", {}),
            dependencies=parallel_ids,
        )
        plan.add_task(agg_task)
        return plan

    # ------------------------------------------------------------------
    # History / introspection
    # ------------------------------------------------------------------

    def get_history(self) -> list[dict]:
        """Get execution history. / 获取执行历史。"""
        return [p.to_dict() for p in self._execution_history]

    def get_context(self) -> AgentContext:
        """Get the execution context. / 获取执行上下文。"""
        return self.context
