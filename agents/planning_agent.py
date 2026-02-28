"""Planning Agent — task decomposition and strategy planning.
规划 Agent — 任务分解与策略规划。

Breaks complex requests into sub-task DAGs, identifying required
Skills and Tools for each step.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent
from agents.message import AgentMessage, MessageType

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

    def validate_dag(self) -> None:
        """Verify no cycles exist in dependencies. / 验证依赖无环。"""
        node_ids = {n.id for n in self.nodes}
        adj: dict[str, list[str]] = {n.id: list(n.dependencies) for n in self.nodes}
        visited: set[str] = set()
        in_stack: set[str] = set()

        def _dfs(nid: str) -> None:
            if nid in in_stack:
                raise ValueError(f"Cycle detected involving task '{nid}'")
            if nid in visited:
                return
            in_stack.add(nid)
            for dep in adj.get(nid, []):
                if dep in node_ids:
                    _dfs(dep)
            in_stack.discard(nid)
            visited.add(nid)

        for n in self.nodes:
            _dfs(n.id)

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


class PlanningAgent(BaseAgent):
    """Planning Agent for task decomposition.
    任务分解规划 Agent。

    Analyzes complex requests and produces structured task plans
    that the Orchestrator can execute.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_capabilities(self) -> list[str]:
        return ["task_decomposition", "dependency_analysis", "plan_generation", "strategy_selection"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "plan")
        params = message.content.get("params", {})

        if action == "replan":
            original_plan_data = params.get("original_plan", {})
            failed_tasks = params.get("failed_tasks", [])
            # Reconstruct TaskPlan from dict
            original = TaskPlan(objective=original_plan_data.get("objective", ""))
            for t in original_plan_data.get("tasks", []):
                original.add_node(TaskNode(
                    id=t["id"],
                    description=t.get("description", ""),
                    tool_or_skill=t.get("tool_or_skill", ""),
                    params=t.get("params", {}),
                    dependencies=t.get("dependencies", []),
                    status=t.get("status", "pending"),
                ))
            new_plan = self.replan(original, failed_tasks, params.get("context"))
            return message.reply({"plan": new_plan.to_dict(), "replanned": True})

        user_input = params.get("user_input", params.get("query", ""))
        context = params.get("context")
        plan = self.plan(user_input, context)
        return message.reply({"plan": plan})

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
        "leak_diagnosis": [
            TaskNode("balance", "Calculate water balance", "calc_full_plant_balance"),
            TaskNode("anomaly", "Detect balance anomaly", "detect_balance_anomaly",
                     dependencies=["balance"]),
            TaskNode("detect", "GNN leak detection", "detect_leak",
                     dependencies=["anomaly"]),
            TaskNode("localize", "Localize leak segment", "localize_leak",
                     dependencies=["detect"]),
        ],
        "evap_optimization": [
            TaskNode("tower", "Predict cooling tower evap", "predict_evaporation"),
            TaskNode("calcination", "Predict calcination evap", "predict_calcination_evap"),
            TaskNode("total", "Predict total evap loss", "predict_total_evap_loss",
                     dependencies=["tower", "calcination"]),
            TaskNode("evaluate", "Evaluate water KPI", "evaluate_water_kpi",
                     dependencies=["total"]),
        ],
        "water_dispatch": [
            TaskNode("demand", "Predict water demand", "predict_demand"),
            TaskNode("evap", "Predict evaporation", "predict_evaporation"),
            TaskNode("dispatch", "Optimize global dispatch", "optimize_global_dispatch",
                     dependencies=["demand", "evap"]),
            TaskNode("odd_check", "Check alumina ODD", "check_alumina_odd",
                     dependencies=["dispatch"]),
        ],
        "daily_report": [
            TaskNode("balance", "Calculate water balance", "calc_full_plant_balance"),
            TaskNode("anomaly", "Detect anomalies", "detect_balance_anomaly",
                     dependencies=["balance"]),
            TaskNode("kpi", "Evaluate water KPI", "evaluate_water_kpi",
                     dependencies=["balance"]),
            TaskNode("evap", "Predict total evap loss", "predict_total_evap_loss"),
        ],
    }

    # Keyword → template mapping for semantic matching
    _TEMPLATE_KEYWORDS: dict[str, tuple[list[str], str]] = {
        "compare_controllers": (
            ["比较", "对比", "compare", "vs", "pid", "mpc", "控制器", "controller"],
            "Compare PID and MPC controllers",
        ),
        "full_analysis": (
            ["完整分析", "full analysis", "全面分析", "comprehensive"],
            "Full system analysis",
        ),
        "leak_diagnosis": (
            ["泄漏", "漏水", "leak", "leakage", "管道检测", "pipe"],
            "Leak diagnosis pipeline",
        ),
        "evap_optimization": (
            ["蒸发", "evaporation", "evap", "冷却塔", "cooling tower"],
            "Evaporation optimization",
        ),
        "water_dispatch": (
            ["调度", "dispatch", "配水", "water allocation", "全局调度"],
            "Water dispatch optimization",
        ),
        "daily_report": (
            ["日报", "daily report", "运营报告", "日常报告"],
            "Daily operations report",
        ),
    }

    def plan(self, user_input: str, context: dict | None = None) -> TaskPlan:
        """Generate a task plan for a complex request.
        为复杂请求生成任务计划。

        Uses keyword matching to select from available plan templates.
        Supports cross-domain workflows via expanded template library.

        Args:
            user_input: User's natural language request / 用户自然语言请求
            context: Additional context / 附加上下文

        Returns:
            TaskPlan with ordered task nodes.
        """
        input_lower = user_input.lower()

        # Score each template by keyword match count
        best_template = None
        best_score = 0
        best_objective = ""

        for template_name, (keywords, objective) in self._TEMPLATE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > best_score:
                best_score = score
                best_template = template_name
                best_objective = objective

        # Use template if we have a match (at least 1 keyword)
        if best_template and best_score >= 1:
            plan = TaskPlan(objective=best_objective)
            for node in self.PLAN_TEMPLATES[best_template]:
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

    def replan(
        self,
        original_plan: TaskPlan,
        failed_tasks: list[str],
        context: dict | None = None,
    ) -> TaskPlan:
        """Generate a revised plan after task failures.
        在任务失败后生成修订计划。

        Removes failed tasks and their dependents, keeping completed work.

        Args:
            original_plan: The original plan that had failures
            failed_tasks: IDs of failed tasks
            context: Additional context for replanning

        Returns:
            Revised TaskPlan with failed branches removed.
        """
        failed_set = set(failed_tasks)

        # Find all tasks that transitively depend on failed tasks
        def _depends_on_failed(node: TaskNode) -> bool:
            return any(d in failed_set for d in node.dependencies)

        blocked_ids = set()
        changed = True
        while changed:
            changed = False
            for node in original_plan.nodes:
                if node.id not in blocked_ids and node.id not in failed_set:
                    if any(d in failed_set or d in blocked_ids for d in node.dependencies):
                        blocked_ids.add(node.id)
                        changed = True

        # Build new plan with only viable tasks
        new_plan = TaskPlan(objective=f"[Replanned] {original_plan.objective}")
        for node in original_plan.nodes:
            if node.id in failed_set or node.id in blocked_ids:
                continue
            if node.status == "completed":
                continue  # already done
            new_node = copy.deepcopy(node)
            # Remove dependencies on completed tasks (they're already done)
            new_node.dependencies = [
                d for d in new_node.dependencies
                if d not in failed_set and d not in blocked_ids
            ]
            new_plan.add_node(new_node)

        return new_plan
