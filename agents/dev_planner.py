"""Development Planner Agent — requirement analysis and task planning.
开发规划 Agent — 需求分析与任务拆解。

Analyzes development requirements, identifies affected modules,
and produces a structured implementation plan (DAG).
Follows ChatDev/MetaGPT-style SOP for software development.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent
from agents.message import AgentMessage, MessageType
from agents.planning_agent import TaskNode, TaskPlan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RequirementSpec:
    """Structured requirement specification. / 结构化需求说明。"""

    title: str
    description: str
    category: str = "feature"  # feature, bugfix, refactor, test, docs
    priority: str = "medium"   # low, medium, high, critical
    affected_layers: list[str] = field(default_factory=list)
    affected_modules: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    estimated_complexity: str = "medium"  # low, medium, high

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "affected_layers": self.affected_layers,
            "affected_modules": self.affected_modules,
            "acceptance_criteria": self.acceptance_criteria,
            "estimated_complexity": self.estimated_complexity,
        }


@dataclass
class DesignDoc:
    """Design document produced by the planner. / 规划产出的设计文档。"""

    requirement: RequirementSpec
    architecture_notes: str = ""
    implementation_plan: TaskPlan = field(default_factory=TaskPlan)
    api_changes: list[dict] = field(default_factory=list)
    test_strategy: str = ""
    risk_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "requirement": self.requirement.to_dict(),
            "architecture_notes": self.architecture_notes,
            "implementation_plan": self.implementation_plan.to_dict(),
            "api_changes": self.api_changes,
            "test_strategy": self.test_strategy,
            "risk_notes": self.risk_notes,
        }


# ---------------------------------------------------------------------------
# Layer / module constants
# ---------------------------------------------------------------------------

LAYER_MAP = {
    "L0": "core",
    "L1": "compute",
    "L2": "mcp_servers",
    "L3": "skills",
    "L4": "agents",
    "web": "web",
}

MODULE_KEYWORDS: dict[str, list[str]] = {
    "simulation": [
        "仿真", "模拟", "水箱", "tank", "simulat", "network", "digital twin",
    ],
    "control": ["控制", "PID", "MPC", "control", "controller"],
    "prediction": ["预测", "预报", "forecast", "predict"],
    "water_balance": ["水平衡", "balance", "残差", "residual"],
    "evaporation": ["蒸发", "冷却塔", "evaporation", "cooling tower", "merkel"],
    "detection": ["泄漏", "检测", "leak", "detect", "GNN", "acoustic"],
    "scheduling": ["调度", "优化", "schedule", "dispatch", "LP"],
    "evaluation": ["评估", "KPI", "evaluate", "WNAL"],
    "odd": ["ODD", "安全", "边界", "safety", "boundary"],
    "design": ["设计", "选型", "尺寸", "sizing", "sensitivity"],
    "data_clean": ["清洗", "插值", "outlier", "clean"],
    "reuse": ["回用", "复用", "reuse", "quality matching"],
    "process_coupling": ["工艺", "耦合", "bayer", "alumina", "process"],
}


# ---------------------------------------------------------------------------
# DevPlannerAgent
# ---------------------------------------------------------------------------

class DevPlannerAgent(BaseAgent):
    """Development Planner — analyses requirements and generates plans.
    开发规划 Agent — 分析需求并生成实施计划。

    Inspired by MetaGPT Product Manager + Architect roles.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_capabilities(self) -> list[str]:
        return ["requirement_analysis", "plan_generation", "design_doc", "task_decomposition"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "plan")
        params = message.content.get("params", {})
        if action == "plan":
            result = self.plan(params.get("user_input", params.get("query", "")), params.get("context"))
        elif action == "analyse_requirement":
            req = self.analyse_requirement(params.get("user_input", ""))
            result = req.to_dict()
        else:
            return message.error_reply(f"Unknown dev_planner action: {action}")
        return message.reply(result)

    # Pre-defined plan templates for common development tasks
    PLAN_TEMPLATES: dict[str, list[TaskNode]] = {
        "new_core_module": [
            TaskNode("design", "设计模块接口和数据结构", "dev_planner"),
            TaskNode("implement", "实现核心算法", "dev_coder",
                     dependencies=["design"]),
            TaskNode("unit_test", "编写单元测试", "dev_tester",
                     dependencies=["implement"]),
            TaskNode("review", "代码审查", "dev_reviewer",
                     dependencies=["implement", "unit_test"]),
            TaskNode("integrate", "集成到上层（MCP/Skill）", "dev_coder",
                     dependencies=["review"]),
            TaskNode("integration_test", "集成测试", "dev_tester",
                     dependencies=["integrate"]),
        ],
        "new_skill": [
            TaskNode("design", "分析技能工作流步骤", "dev_planner"),
            TaskNode("implement", "实现 Skill 类", "dev_coder",
                     dependencies=["design"]),
            TaskNode("yaml_meta", "编写 YAML 元数据", "dev_coder",
                     dependencies=["design"]),
            TaskNode("test", "编写技能测试", "dev_tester",
                     dependencies=["implement"]),
            TaskNode("review", "代码审查", "dev_reviewer",
                     dependencies=["implement", "test"]),
            TaskNode("register", "注册到 Orchestrator", "dev_coder",
                     dependencies=["review"]),
        ],
        "new_agent": [
            TaskNode("design", "定义 Agent 能力和接口", "dev_planner"),
            TaskNode("card", "编写 Agent Card JSON", "dev_coder",
                     dependencies=["design"]),
            TaskNode("implement", "实现 Agent 类", "dev_coder",
                     dependencies=["design"]),
            TaskNode("test", "编写 Agent 测试", "dev_tester",
                     dependencies=["implement"]),
            TaskNode("review", "代码审查", "dev_reviewer",
                     dependencies=["implement", "test"]),
            TaskNode("register", "在 __init__.py 中注册", "dev_coder",
                     dependencies=["review"]),
        ],
        "bugfix": [
            TaskNode("diagnose", "定位 Bug 根因", "dev_planner"),
            TaskNode("fix", "实现修复", "dev_coder",
                     dependencies=["diagnose"]),
            TaskNode("regression_test", "回归测试", "dev_tester",
                     dependencies=["fix"]),
            TaskNode("review", "修复审查", "dev_reviewer",
                     dependencies=["fix", "regression_test"]),
        ],
        "refactor": [
            TaskNode("analyse", "分析重构范围和影响", "dev_planner"),
            TaskNode("snapshot_tests", "快照现有测试结果", "dev_tester",
                     dependencies=["analyse"]),
            TaskNode("refactor", "执行重构", "dev_coder",
                     dependencies=["snapshot_tests"]),
            TaskNode("verify_tests", "验证测试不回退", "dev_tester",
                     dependencies=["refactor"]),
            TaskNode("review", "重构审查", "dev_reviewer",
                     dependencies=["refactor", "verify_tests"]),
        ],
    }

    def analyse_requirement(self, user_input: str) -> RequirementSpec:
        """Analyse user input and produce a structured requirement.
        分析用户输入，产出结构化需求。
        """
        input_lower = user_input.lower()

        # Determine category
        category = "feature"
        if any(kw in input_lower for kw in ["bug", "修复", "fix", "错误"]):
            category = "bugfix"
        elif any(kw in input_lower for kw in ["重构", "refactor", "优化代码"]):
            category = "refactor"
        elif any(kw in input_lower for kw in ["测试", "test", "覆盖率"]):
            category = "test"
        elif any(kw in input_lower for kw in ["文档", "doc", "readme"]):
            category = "docs"

        # Identify affected layers
        layers = []
        for layer_key, layer_dir in LAYER_MAP.items():
            if layer_dir in input_lower or layer_key.lower() in input_lower:
                layers.append(layer_key)
        if not layers:
            layers = self._infer_layers(input_lower)

        # Identify affected modules
        modules = []
        for mod_name, keywords in MODULE_KEYWORDS.items():
            if any(kw.lower() in input_lower for kw in keywords):
                modules.append(mod_name)

        # Determine complexity
        complexity = "low"
        if len(modules) > 2 or len(layers) > 2:
            complexity = "high"
        elif len(modules) > 1 or len(layers) > 1:
            complexity = "medium"

        # Determine priority
        priority = "medium"
        if any(kw in input_lower for kw in ["紧急", "urgent", "critical"]):
            priority = "critical"
        elif any(kw in input_lower for kw in ["重要", "important", "high"]):
            priority = "high"

        return RequirementSpec(
            title=user_input[:80],
            description=user_input,
            category=category,
            priority=priority,
            affected_layers=layers,
            affected_modules=modules,
            estimated_complexity=complexity,
        )

    def generate_plan(
        self,
        requirement: RequirementSpec,
        context: dict | None = None,
    ) -> DesignDoc:
        """Generate a design doc with implementation plan.
        生成包含实施计划的设计文档。
        """
        # Select plan template based on category and context
        template_key = self._select_template(requirement, context)
        template = self.PLAN_TEMPLATES.get(template_key, [])

        plan = TaskPlan(objective=requirement.title)
        for node in template:
            node_copy = copy.deepcopy(node)
            node_copy.params["requirement"] = requirement.to_dict()
            plan.add_node(node_copy)

        plan.validate_dag()

        # Build design doc
        arch_notes = self._generate_arch_notes(requirement)
        test_strategy = self._generate_test_strategy(requirement)
        risk_notes = self._assess_risks(requirement)
        api_changes = self._identify_api_changes(requirement)

        return DesignDoc(
            requirement=requirement,
            architecture_notes=arch_notes,
            implementation_plan=plan,
            api_changes=api_changes,
            test_strategy=test_strategy,
            risk_notes=risk_notes,
        )

    def plan(self, user_input: str, context: dict | None = None) -> dict:
        """End-to-end: analyse → plan → return design doc dict.
        端到端：分析 → 规划 → 返回设计文档字典。
        """
        req = self.analyse_requirement(user_input)
        design = self.generate_plan(req, context)
        logger.info(
            "DevPlanner: generated plan '%s' with %d tasks",
            design.implementation_plan.objective,
            len(design.implementation_plan.nodes),
        )
        return design.to_dict()

    # ----- private helpers -----

    @staticmethod
    def _infer_layers(text: str) -> list[str]:
        """Infer affected layers from keywords."""
        layers = []
        if any(kw in text for kw in ["算法", "模型", "计算", "core"]):
            layers.append("L0")
        if any(kw in text for kw in ["ray", "分布式", "parallel"]):
            layers.append("L1")
        if any(kw in text for kw in ["mcp", "server", "工具"]):
            layers.append("L2")
        if any(kw in text for kw in ["skill", "技能", "工作流"]):
            layers.append("L3")
        if any(kw in text for kw in ["agent", "智能体", "编排"]):
            layers.append("L4")
        if any(kw in text for kw in ["web", "api", "前端", "router"]):
            layers.append("web")
        return layers or ["L0"]

    def _select_template(
        self, req: RequirementSpec, context: dict | None = None,
    ) -> str:
        """Choose the best plan template for the requirement."""
        if req.category == "bugfix":
            return "bugfix"
        if req.category == "refactor":
            return "refactor"
        desc = req.description.lower()
        if any(kw in desc for kw in ["agent", "智能体"]):
            return "new_agent"
        if any(kw in desc for kw in ["skill", "技能", "工作流"]):
            return "new_skill"
        return "new_core_module"

    @staticmethod
    def _generate_arch_notes(req: RequirementSpec) -> str:
        layers_str = ", ".join(req.affected_layers) or "TBD"
        modules_str = ", ".join(req.affected_modules) or "TBD"
        return (
            f"Affected layers: {layers_str}\n"
            f"Affected modules: {modules_str}\n"
            f"Complexity: {req.estimated_complexity}\n"
            f"Follow L0→L4 bottom-up implementation order."
        )

    @staticmethod
    def _generate_test_strategy(req: RequirementSpec) -> str:
        strategies = ["Unit tests for each new/modified function"]
        if req.estimated_complexity in ("medium", "high"):
            strategies.append("Integration tests across layers")
        if "odd" in req.affected_modules or "safety" in req.description.lower():
            strategies.append("Safety boundary tests (ODD zone verification)")
        strategies.append("Run full suite: pytest (1001+ tests must pass)")
        return "; ".join(strategies)

    @staticmethod
    def _assess_risks(req: RequirementSpec) -> str:
        risks = []
        if req.estimated_complexity == "high":
            risks.append("High complexity — consider phased delivery")
        if len(req.affected_layers) > 2:
            risks.append("Cross-layer changes — coordinate API contracts")
        if "detection" in req.affected_modules:
            risks.append("GNN model changes may require retraining")
        if not risks:
            risks.append("Low risk — standard development workflow")
        return "; ".join(risks)

    @staticmethod
    def _identify_api_changes(req: RequirementSpec) -> list[dict]:
        changes = []
        for mod in req.affected_modules:
            changes.append({
                "module": mod,
                "type": "new" if req.category == "feature" else "modify",
                "description": f"Changes in {mod} module",
            })
        return changes
