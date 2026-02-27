"""Orchestrator Agent — main entry point for user interaction.
主编排 Agent — 用户交互主入口。

Responsibilities:
    - Parse user natural language intent
    - Route to appropriate Skill, Tool, or sub-Agent
    - Coordinate multi-step workflows via MessageBus and Executor
    - Return structured results

Routing priority:
    1. Exact match to Skill trigger phrases → call Skill
    2. Match to single MCP Tool → call Tool directly
    3. No match → delegate to Planning Agent for decomposition
    4. Multi-agent → fan-out via Executor DAG
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents.base_agent import BaseAgent
from agents.context import AgentContext
from agents.message import AgentMessage, MessageType
from agents.registry import AgentRegistry
from skills.base_skill import discover_skills

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

TOOL_KEYWORDS.update({
    "calc_node_balance": ["水平衡", "water balance", "节点平衡", "残差"],
    "calc_full_plant_balance": ["全厂水平衡", "全厂核算", "full balance"],
    "detect_leak": ["泄漏检测", "漏水检测", "leak detection", "泄漏"],
    "localize_leak": ["泄漏定位", "漏点定位", "leak localization"],
    "predict_evaporation": ["蒸发预测", "蒸发量", "evaporation prediction"],
    "match_reuse_path": ["回用匹配", "回用路径", "reuse matching"],
    "optimize_reuse_schedule": ["回用调度", "回用优化", "reuse scheduling"],
    "optimize_global_dispatch": ["全局调度", "global dispatch", "取水优化"],
    "simulate_network": ["管网仿真", "管网模拟", "network simulation", "管网"],
    "evaluate_water_kpi": ["水网KPI", "水网指标", "water KPI"],
    "check_alumina_odd": ["氧化铝ODD", "厂区安全", "alumina ODD"],
})


class OrchestratorAgent(BaseAgent):
    """Main orchestration agent for HydroOS multi-agent platform.
    HydroOS 多智能体平台的主编排 Agent。

    This agent implements a four-level routing strategy:
        Level 1: Match Skill trigger phrases → invoke fixed workflow
        Level 2: Match Tool keywords → direct tool call
        Level 3: Capability-based routing → find agent by capability via registry
        Level 4: No match → delegate to Planning Agent for decomposition
    """

    def __init__(self, registry: AgentRegistry | None = None, **kwargs):
        super().__init__(**kwargs)
        self.skills = discover_skills()
        self._skill_instances: dict[str, Any] = {}
        self.registry = registry
        self.context = AgentContext()
        self._load_skill_instances()

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def get_capabilities(self) -> list[str]:
        return [
            "intent_classification", "skill_routing", "tool_invocation",
            "workflow_coordination", "multi_agent_orchestration",
        ]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Handle incoming messages from other agents or the bus.
        处理来自其他 Agent 或总线的传入消息。
        """
        action = message.content.get("action", "handle_request")
        params = message.content.get("params", {})

        if action == "handle_request":
            user_input = params.get("user_input", params.get("query", ""))
            result = await self.handle_request(user_input, params)
            return message.reply(result)
        elif action == "classify_intent":
            user_input = params.get("user_input", "")
            result = self.classify_intent(user_input)
            return message.reply(result)
        elif action == "delegate":
            # Delegate to a specific agent via the registry
            target = params.get("target_agent", "")
            result = await self._delegate_to_agent(target, params)
            return message.reply(result)
        else:
            return message.error_reply(f"Unknown orchestrator action: {action}")

    # ------------------------------------------------------------------
    # Skill loading (backward compatible)
    # ------------------------------------------------------------------

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

        skill_classes.update({
            "leak_diagnosis": "skills.leak_diagnosis.LeakDiagnosisSkill",
            "evap_optimization": "skills.evap_optimization.EvapOptimizationSkill",
            "reuse_scheduling": "skills.reuse_scheduling.ReuseSchedulingSkill",
            "global_dispatch": "skills.global_dispatch.GlobalDispatchSkill",
            "daily_report": "skills.daily_report.DailyReportSkill",
        })

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

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

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

        # Level 3: Capability-based routing via registry
        if self.registry:
            capability_match = self._match_capability(input_lower)
            if capability_match:
                return capability_match

        # Level 4: Flexible analysis
        return {
            "route_type": "agent",
            "target": "planning",
            "confidence": 0.3,
            "message": "No direct match found; delegating to Planning Agent",
        }

    def _match_capability(self, input_lower: str) -> dict | None:
        """Try to match input to a registered agent's capability.
        尝试将输入匹配到已注册 Agent 的能力。
        """
        if not self.registry:
            return None

        capability_keywords = {
            "code_review": ["代码审查", "code review", "review code"],
            "test_generation": ["生成测试", "generate test", "test generation"],
            "domain_qa": ["知识问答", "domain question", "knowledge query"],
            "rl_dispatch": ["强化学习调度", "rl dispatch", "reinforcement"],
            "report_generation": ["生成报告", "generate report", "report"],
            "dev_pipeline": ["开发流水线", "dev pipeline", "collaborative dev"],
        }

        for capability, keywords in capability_keywords.items():
            if any(kw in input_lower for kw in keywords):
                agents = self.registry.find_by_capability(capability)
                if agents:
                    return {
                        "route_type": "agent",
                        "target": agents[0].agent_id,
                        "confidence": 0.6,
                        "capability": capability,
                        "message": f"Routing to {agents[0].__class__.__name__} via capability match",
                    }
        return None

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

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

        # Record in context
        self.context.add_trace(self.agent_id, "classify_intent", {
            "input": user_input[:100],
            "intent": intent,
        })

        if intent["route_type"] == "skill":
            return await self._execute_skill(intent["target"], params)
        elif intent["route_type"] == "tool":
            return await self._execute_tool(intent["target"], params)
        elif intent["route_type"] == "agent" and intent["target"] != "planning":
            return await self._delegate_to_agent(intent["target"], params)
        else:
            return {
                "status": "delegated",
                "intent": intent,
                "message": "Complex request — would be handled by Planning + Analysis Agents",
            }

    async def _execute_skill(self, skill_name: str, params: dict) -> dict:
        """Execute a Skill by name. / 按名称执行 Skill。"""
        if skill_name not in self._skill_instances:
            available = list(self._skill_instances.keys())
            return {
                "error": f"Skill '{skill_name}' not loaded. "
                         f"Available: {available}",
            }

        skill = self._skill_instances[skill_name]
        result = await skill.run(params)

        self.context.add_trace(self.agent_id, f"skill:{skill_name}", {
            "success": result.success,
            "execution_time": result.execution_time,
        })

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
        from skills.base_skill import _call_tool_dynamic

        try:
            result = await asyncio.to_thread(_call_tool_dynamic, tool_name, params)
            self.context.add_trace(self.agent_id, f"tool:{tool_name}", {"status": "completed"})
            return {"status": "completed", "tool": tool_name, "data": result}
        except Exception as e:
            self.context.add_trace(self.agent_id, f"tool:{tool_name}", {"error": str(e)})
            return {"status": "failed", "tool": tool_name, "error": str(e)}

    async def _delegate_to_agent(self, agent_id: str, params: dict) -> dict:
        """Delegate a task to another agent via the registry / message bus.
        通过注册表/消息总线将任务委托给另一个 Agent。
        """
        if not self.registry:
            return {
                "status": "delegated",
                "target": agent_id,
                "message": "No registry configured — delegation not executed",
            }

        agent = self.registry.get_agent(agent_id)
        if agent is None:
            return {
                "status": "failed",
                "error": f"Agent '{agent_id}' not found in registry",
            }

        message = AgentMessage(
            type=MessageType.REQUEST,
            sender=self.agent_id,
            recipient=agent_id,
            content={
                "action": params.get("action", "handle_request"),
                "params": params,
            },
        )

        try:
            response = await agent.handle_message(message)
            self.context.add_trace(self.agent_id, f"delegate:{agent_id}", {
                "status": "completed",
            })
            return {
                "status": "completed",
                "delegated_to": agent_id,
                "data": response.content,
            }
        except Exception as e:
            self.context.add_trace(self.agent_id, f"delegate:{agent_id}", {"error": str(e)})
            return {
                "status": "failed",
                "delegated_to": agent_id,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Multi-agent collaboration
    # ------------------------------------------------------------------

    async def run_collaborative_workflow(
        self,
        objective: str,
        agent_tasks: list[dict],
    ) -> dict:
        """Run a collaborative workflow across multiple agents.
        跨多个 Agent 运行协作工作流。

        Args:
            objective: Workflow objective description
            agent_tasks: List of {agent_id, action, params, dependencies} dicts

        Returns:
            Workflow execution result.
        """
        from agents.executor import ExecutionPlan, ExecutionTask, MultiAgentExecutor

        if not self.registry:
            return {"status": "failed", "error": "No registry configured for multi-agent execution"}

        executor = MultiAgentExecutor(self.registry, self.context)

        plan = ExecutionPlan(objective=objective)
        for i, task_def in enumerate(agent_tasks):
            task = ExecutionTask(
                id=task_def.get("id", f"task_{i+1}"),
                agent_id=task_def["agent_id"],
                action=task_def["action"],
                params=task_def.get("params", {}),
                dependencies=task_def.get("dependencies", []),
            )
            plan.add_task(task)

        result = await executor.execute(plan)

        self.context.add_trace(self.agent_id, "collaborative_workflow", {
            "plan_id": result.id,
            "status": result.status.value,
            "n_tasks": len(result.tasks),
        })

        return result.to_dict()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

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

    def get_registered_agents(self) -> list[dict]:
        """List all agents registered in the registry.
        列出注册表中所有已注册的 Agent。
        """
        if not self.registry:
            return []
        return [
            {
                "id": agent.agent_id,
                "type": agent.__class__.__name__,
                "capabilities": agent.get_capabilities(),
                "status": agent.status.value,
            }
            for agent in self.registry.get_all_agents().values()
        ]

    def get_platform_summary(self) -> dict:
        """Get a full platform summary including skills, agents, tools.
        获取包括技能、智能体、工具在内的完整平台摘要。
        """
        return {
            "skills_count": len(self.skills),
            "skill_instances_count": len(self._skill_instances),
            "tools_count": len(TOOL_KEYWORDS),
            "registered_agents": self.get_registered_agents(),
            "context_keys": self.context.keys(),
            "has_registry": self.registry is not None,
        }
