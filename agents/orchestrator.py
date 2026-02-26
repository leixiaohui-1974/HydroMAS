"""Orchestrator Agent — main entry point for user interaction.
主编排 Agent — 用户交互主入口。

Responsibilities:
    - Parse user natural language intent
    - Route to appropriate Skill, Tool, or sub-Agent
    - Coordinate multi-step workflows
    - Return structured results

Routing priority:
    1. Exact match to Skill trigger phrases → call Skill
    2. Match to single MCP Tool → call Tool directly
    3. No match → delegate to Planning Agent for decomposition
"""

from __future__ import annotations

import logging
from typing import Any

from skills.base_skill import discover_skills, SkillMetadata

logger = logging.getLogger(__name__)


# Intent categories for routing
TOOL_KEYWORDS = {
    "simulate_tank": ["仿真", "模拟", "simulate", "simulation", "阶跃响应", "step response"],
    "identify_parameters": ["辨识", "identify", "参数反演", "parameter estimation"],
    "clean_timeseries": ["清洗", "clean", "去噪", "denoise"],
    "predict_future": ["预测", "predict", "预报", "forecast"],
    "optimize_schedule": ["调度", "schedule", "分配", "allocate"],
    "run_controller": ["控制", "control", "PID", "MPC"],
    "check_odd": ["ODD", "安全", "safety", "边界", "boundary"],
    "evaluate_performance": ["评价", "evaluate", "评估", "assess", "指标", "metric"],
    "optimize_design": ["设计", "design", "优化", "sizing", "尺寸"],
}


class OrchestratorAgent:
    """Main orchestration agent for HydroOS multi-agent platform.
    HydroOS 多智能体平台的主编排 Agent。

    This agent implements a three-level routing strategy:
        Level 1: Match Skill trigger phrases → invoke fixed workflow
        Level 2: Match Tool keywords → direct tool call
        Level 3: No match → flexible analysis via sub-agents
    """

    def __init__(self):
        self.skills = discover_skills()
        self._skill_instances: dict[str, Any] = {}
        self._load_skill_instances()

    def _load_skill_instances(self) -> None:
        """Load Skill class instances. / 加载 Skill 类实例。"""
        skill_classes = {
            "control_system_design": "skills.control_system_design.ControlSystemDesignSkill",
            "data_analysis_predict": "skills.data_analysis_predict.DataAnalysisPredictSkill",
            "odd_assessment": "skills.odd_assessment.ODDAssessmentSkill",
            "optimization_design": "skills.optimization_design.OptimizationDesignSkill",
            "full_lifecycle": "skills.full_lifecycle.FullLifecycleSkill",
            "forecast_skill": "skills.forecast_skill.ForecastSkill",
            "warning_skill": "skills.warning_skill.WarningSkill",
            "rehearsal_skill": "skills.rehearsal_skill.RehearsalSkill",
            "plan_skill": "skills.plan_skill.PlanSkill",
            "four_prediction_loop": "skills.four_prediction_loop.FourPredictionLoopSkill",
        }

        import importlib
        for name, class_path in skill_classes.items():
            try:
                module_path, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name)
                meta = self.skills.get(name)
                self._skill_instances[name] = cls(metadata=meta)
            except Exception as e:
                logger.warning(f"Failed to load skill {name}: {e}")

    def classify_intent(self, user_input: str) -> dict:
        """Classify user intent and determine routing.
        分类用户意图并确定路由。

        Args:
            user_input: Natural language input from user / 用户自然语言输入

        Returns:
            Dict with route_type, target, and confidence.
        """
        input_lower = user_input.lower()

        # Level 1: Check Skill trigger phrases
        best_skill = None
        best_score = 0
        for skill_name, meta in self.skills.items():
            for phrase in meta.trigger_phrases:
                if phrase.lower() in input_lower:
                    score = len(phrase)
                    if score > best_score:
                        best_score = score
                        best_skill = skill_name

        if best_skill:
            return {
                "route_type": "skill",
                "target": best_skill,
                "confidence": min(1.0, best_score / 10),
                "display_name": self.skills[best_skill].display_name,
            }

        # Level 2: Check Tool keywords
        best_tool = None
        best_score = 0
        for tool_name, keywords in TOOL_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in input_lower:
                    score = len(kw)
                    if score > best_score:
                        best_score = score
                        best_tool = tool_name

        if best_tool:
            return {
                "route_type": "tool",
                "target": best_tool,
                "confidence": min(1.0, best_score / 8),
            }

        # Level 3: Flexible analysis
        return {
            "route_type": "agent",
            "target": "planning",
            "confidence": 0.3,
            "message": "No direct match found; delegating to Planning Agent",
        }

    async def handle_request(self, user_input: str, params: dict | None = None) -> dict:
        """Handle a user request end-to-end.
        端到端处理用户请求。

        Args:
            user_input: Natural language input / 用户自然语言输入
            params: Additional parameters / 附加参数

        Returns:
            Response dict with results.
        """
        intent = self.classify_intent(user_input)
        params = params or {}

        if intent["route_type"] == "skill":
            return await self._execute_skill(intent["target"], params)
        elif intent["route_type"] == "tool":
            return await self._execute_tool(intent["target"], params)
        else:
            return {
                "status": "delegated",
                "intent": intent,
                "message": "Complex request — would be handled by Planning + Analysis Agents",
            }

    async def _execute_skill(self, skill_name: str, params: dict) -> dict:
        """Execute a Skill by name. / 按名称执行 Skill。"""
        if skill_name not in self._skill_instances:
            return {"error": f"Skill '{skill_name}' not loaded"}

        skill = self._skill_instances[skill_name]
        result = await skill.run(params)

        return {
            "status": "completed" if result.success else "failed",
            "skill": skill_name,
            "data": result.data,
            "error": result.error,
            "execution_time": result.execution_time,
            "steps_completed": result.steps_completed,
        }

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        """Execute a single MCP Tool. / 执行单个 MCP 工具。"""
        from skills.base_skill import BaseSkill

        # Use BaseSkill's dynamic tool calling
        class _ToolCaller(BaseSkill):
            async def execute(self, p):
                pass

        caller = _ToolCaller()
        try:
            result = caller._call_tool_dynamic(tool_name, params)
            return {"status": "completed", "tool": tool_name, "data": result}
        except Exception as e:
            return {"status": "failed", "tool": tool_name, "error": str(e)}

    def get_available_skills(self) -> list[dict]:
        """List all available Skills. / 列出所有可用 Skill。"""
        return [
            {
                "name": meta.name,
                "display_name": meta.display_name,
                "description": meta.description,
                "trigger_phrases": meta.trigger_phrases,
            }
            for meta in self.skills.values()
        ]
