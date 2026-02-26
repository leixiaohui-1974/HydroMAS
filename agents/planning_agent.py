"""Planning Agent — task decomposition and strategy planning.
规划 Agent — 任务分解与策略规划。

Breaks complex requests into sub-task DAGs, identifying required
Skills and Tools for each step.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskNode:
    """A node in the task DAG. / 任务 DAG 中的节点。"""

    id: str
    description: str
    tool_or_skill: str
    params: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed


@dataclass
class TaskPlan:
    """A directed acyclic graph of tasks. / 任务有向无环图。"""

    nodes: list[TaskNode] = field(default_factory=list)
    objective: str = ""

    def add_node(self, node: TaskNode) -> None:
        self.nodes.append(node)

    def get_ready_tasks(self) -> list[TaskNode]:
        """Get tasks whose dependencies are all completed. / 获取依赖已完成的任务。"""
        completed_ids = {n.id for n in self.nodes if n.status == "completed"}
        return [
            n for n in self.nodes
            if n.status == "pending" and all(d in completed_ids for d in n.dependencies)
        ]

    def to_dict(self) -> dict:
        return {
            "objective": self.objective,
            "tasks": [
                {
                    "id": n.id,
                    "description": n.description,
                    "tool_or_skill": n.tool_or_skill,
                    "dependencies": n.dependencies,
                    "status": n.status,
                }
                for n in self.nodes
            ],
        }


class PlanningAgent:
    """Planning Agent for task decomposition.
    任务分解规划 Agent。

    Analyzes complex requests and produces structured task plans
    that the Orchestrator can execute.
    """

    # Templates for common complex requests
    PLAN_TEMPLATES = {
        "compare_controllers": [
            TaskNode("sim_pid", "PID control simulation", "run_controller",
                     {"controller_type": "PID"}),
            TaskNode("sim_mpc", "MPC control simulation", "run_controller",
                     {"controller_type": "MPC"}),
            TaskNode("eval_pid", "Evaluate PID performance", "evaluate_performance",
                     dependencies=["sim_pid"]),
            TaskNode("eval_mpc", "Evaluate MPC performance", "evaluate_performance",
                     dependencies=["sim_mpc"]),
        ],
        "full_analysis": [
            TaskNode("clean", "Clean input data", "clean_timeseries"),
            TaskNode("predict", "Predict future values", "predict_future",
                     dependencies=["clean"]),
            TaskNode("simulate", "Run simulation", "simulate_tank"),
            TaskNode("odd_check", "Check ODD boundaries", "check_odd",
                     dependencies=["predict"]),
            TaskNode("evaluate", "Evaluate results", "evaluate_performance",
                     dependencies=["predict", "simulate"]),
        ],
    }

    def plan(self, user_input: str, context: dict | None = None) -> TaskPlan:
        """Generate a task plan for a complex request.
        为复杂请求生成任务计划。

        Args:
            user_input: User's natural language request / 用户自然语言请求
            context: Additional context / 附加上下文

        Returns:
            TaskPlan with ordered task nodes.
        """
        input_lower = user_input.lower()

        # Match against plan templates
        if any(kw in input_lower for kw in ["比较", "对比", "compare", "vs"]):
            if any(kw in input_lower for kw in ["pid", "mpc", "控制器", "controller"]):
                plan = TaskPlan(objective="Compare PID and MPC controllers")
                for node in self.PLAN_TEMPLATES["compare_controllers"]:
                    plan.add_node(copy.deepcopy(node))
                return plan

        if any(kw in input_lower for kw in ["完整分析", "full analysis", "全面"]):
            plan = TaskPlan(objective="Full system analysis")
            for node in self.PLAN_TEMPLATES["full_analysis"]:
                plan.add_node(copy.deepcopy(node))
            return plan

        # Default: single-task plan
        plan = TaskPlan(objective=user_input)
        plan.add_node(TaskNode(
            id="task_1",
            description=user_input,
            tool_or_skill="planning",
            params=context or {},
        ))
        return plan
