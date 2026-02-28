"""Shared web-layer singletons and dependencies.
Web 层共享的单例与依赖注入。
"""

from __future__ import annotations

import threading

_lock = threading.RLock()


def get_orchestrator():
    """Get or create the singleton OrchestratorAgent (thread-safe)."""
    if not hasattr(get_orchestrator, "_instance"):
        with _lock:
            if not hasattr(get_orchestrator, "_instance"):
                from agents.orchestrator import OrchestratorAgent
                get_orchestrator._instance = OrchestratorAgent()
    return get_orchestrator._instance


def get_report_agent():
    """Get or create the singleton ReportAgent (thread-safe)."""
    if not hasattr(get_report_agent, "_instance"):
        with _lock:
            if not hasattr(get_report_agent, "_instance"):
                from agents.report_agent import ReportAgent
                get_report_agent._instance = ReportAgent()
    return get_report_agent._instance


def get_agent_registry():
    """Get or create the singleton AgentRegistry with all platform agents.
    获取或创建单例 AgentRegistry，注册所有平台 Agent。
    """
    if not hasattr(get_agent_registry, "_instance"):
        with _lock:
            if not hasattr(get_agent_registry, "_instance"):
                from agents.registry import AgentRegistry

                registry = AgentRegistry()
                bus = get_message_bus()
                registry.connect_bus(bus)

                # Register domain agents
                from agents.orchestrator import OrchestratorAgent
                from agents.planning_agent import PlanningAgent
                from agents.analysis_agent import AnalysisAgent
                from agents.report_agent import ReportAgent
                from agents.safety_agent import SafetyAgent
                from agents.handuo_agent import HanduoAgent
                from agents.rl_dispatch_agent import RLDispatchAgent

                for cls, aid in [
                    (OrchestratorAgent, "orchestrator"),
                    (PlanningAgent, "planning"),
                    (AnalysisAgent, "analysis"),
                    (ReportAgent, "report"),
                    (SafetyAgent, "safety"),
                    (HanduoAgent, "handuo"),
                    (RLDispatchAgent, "rl_dispatch"),
                ]:
                    registry.register(cls(agent_id=aid))

                # Register devops agents
                from agents.dev_planner import DevPlannerAgent
                from agents.dev_reviewer import DevReviewerAgent
                from agents.dev_tester import DevTesterAgent
                from agents.dev_orchestrator import DevOrchestratorAgent

                for cls, aid in [
                    (DevPlannerAgent, "dev_planner"),
                    (DevReviewerAgent, "dev_reviewer"),
                    (DevTesterAgent, "dev_tester"),
                    (DevOrchestratorAgent, "dev_orchestrator"),
                ]:
                    registry.register(cls(agent_id=aid))

                # Register content agents
                from openclaw.agents.content_planner import ContentPlannerAgent
                from openclaw.agents.content_reviewer import ContentReviewerAgent
                from openclaw.agents.content_publisher import ContentPublisherAgent
                from openclaw.agents.content_orchestrator import ContentOrchestratorAgent

                for cls, aid in [
                    (ContentPlannerAgent, "content_planner"),
                    (ContentReviewerAgent, "content_reviewer"),
                    (ContentPublisherAgent, "content_publisher"),
                    (ContentOrchestratorAgent, "content_orchestrator"),
                ]:
                    registry.register(cls(agent_id=aid))

                get_agent_registry._instance = registry
    return get_agent_registry._instance


def get_message_bus():
    """Get or create the singleton MessageBus (thread-safe).
    获取或创建单例 MessageBus（线程安全）。
    """
    if not hasattr(get_message_bus, "_instance"):
        with _lock:
            if not hasattr(get_message_bus, "_instance"):
                from agents.message import MessageBus
                get_message_bus._instance = MessageBus()
    return get_message_bus._instance


def get_agent_context():
    """Get or create the singleton AgentContext (thread-safe).
    获取或创建单例 AgentContext（线程安全）。
    """
    if not hasattr(get_agent_context, "_instance"):
        with _lock:
            if not hasattr(get_agent_context, "_instance"):
                from agents.context import AgentContext
                get_agent_context._instance = AgentContext()
    return get_agent_context._instance


def get_health_monitor():
    """Get or create the singleton AgentHealthMonitor (thread-safe).
    获取或创建单例 AgentHealthMonitor（线程安全）。
    """
    if not hasattr(get_health_monitor, "_instance"):
        with _lock:
            if not hasattr(get_health_monitor, "_instance"):
                from agents.health import AgentHealthMonitor
                get_health_monitor._instance = AgentHealthMonitor(get_agent_registry())
    return get_health_monitor._instance


def get_span_recorder():
    """Get or create the singleton SpanRecorder (thread-safe).
    获取或创建单例 SpanRecorder（线程安全）。
    """
    if not hasattr(get_span_recorder, "_instance"):
        with _lock:
            if not hasattr(get_span_recorder, "_instance"):
                from agents.tracing import SpanRecorder
                get_span_recorder._instance = SpanRecorder()
    return get_span_recorder._instance


def get_circuit_breakers():
    """Get or create the singleton CircuitBreakerRegistry (thread-safe).
    获取或创建单例 CircuitBreakerRegistry（线程安全）。
    """
    if not hasattr(get_circuit_breakers, "_instance"):
        with _lock:
            if not hasattr(get_circuit_breakers, "_instance"):
                from agents.circuit_breaker import CircuitBreakerRegistry
                get_circuit_breakers._instance = CircuitBreakerRegistry()
    return get_circuit_breakers._instance


def get_rate_limiters():
    """Get or create the singleton AgentRateLimiterRegistry (thread-safe).
    获取或创建单例 AgentRateLimiterRegistry（线程安全）。
    """
    if not hasattr(get_rate_limiters, "_instance"):
        with _lock:
            if not hasattr(get_rate_limiters, "_instance"):
                from agents.rate_limiter import AgentRateLimiterRegistry
                get_rate_limiters._instance = AgentRateLimiterRegistry()
    return get_rate_limiters._instance


def get_executor():
    """Get or create the singleton MultiAgentExecutor (thread-safe).
    获取或创建单例 MultiAgentExecutor（线程安全）。
    """
    if not hasattr(get_executor, "_instance"):
        with _lock:
            if not hasattr(get_executor, "_instance"):
                from agents.executor import MultiAgentExecutor
                get_executor._instance = MultiAgentExecutor(
                    registry=get_agent_registry(),
                    context=get_agent_context(),
                    health_monitor=get_health_monitor(),
                    message_bus=get_message_bus(),
                    span_recorder=get_span_recorder(),
                    circuit_breakers=get_circuit_breakers(),
                    rate_limiters=get_rate_limiters(),
                )
    return get_executor._instance


def get_skill_registry():
    """Get or create the singleton skill registry (thread-safe).
    获取或创建单例 Skill 注册表（线程安全）。

    Returns a dict mapping skill_name → {metadata: SkillMetadata, instance: BaseSkill}.
    """
    if not hasattr(get_skill_registry, "_instance"):
        with _lock:
            if not hasattr(get_skill_registry, "_instance"):
                from skills.base_skill import discover_skills
                from skills import (
                    ForecastSkill, WarningSkill, RehearsalSkill, PlanSkill,
                    FourPredictionLoopSkill, DataAnalysisPredictSkill,
                    ODDAssessmentSkill, ControlSystemDesignSkill,
                    OptimizationDesignSkill, FullLifecycleSkill,
                    LeakDiagnosisSkill, EvapOptimizationSkill,
                    ReuseSchedulingSkill, GlobalDispatchSkill,
                    DailyReportSkill,
                )

                # Discover metadata from YAML files
                metadata_map = discover_skills()

                # Map skill names to their class constructors
                _SKILL_CLASSES = {
                    "forecast_skill": ForecastSkill,
                    "warning_skill": WarningSkill,
                    "rehearsal_skill": RehearsalSkill,
                    "plan_skill": PlanSkill,
                    "four_prediction_loop": FourPredictionLoopSkill,
                    "data_analysis_predict": DataAnalysisPredictSkill,
                    "odd_assessment": ODDAssessmentSkill,
                    "control_system_design": ControlSystemDesignSkill,
                    "optimization_design": OptimizationDesignSkill,
                    "full_lifecycle": FullLifecycleSkill,
                    "leak_diagnosis": LeakDiagnosisSkill,
                    "evap_optimization": EvapOptimizationSkill,
                    "reuse_scheduling": ReuseSchedulingSkill,
                    "global_dispatch": GlobalDispatchSkill,
                    "daily_report": DailyReportSkill,
                }

                registry: dict = {}
                for name, meta in metadata_map.items():
                    cls = _SKILL_CLASSES.get(name)
                    instance = cls(metadata=meta) if cls else None
                    registry[name] = {"metadata": meta, "instance": instance}

                # Register skills that have classes but no YAML
                for name, cls in _SKILL_CLASSES.items():
                    if name not in registry:
                        registry[name] = {"metadata": None, "instance": cls()}

                get_skill_registry._instance = registry
    return get_skill_registry._instance


def get_intent_classifier():
    """Get or create the singleton IntentClassifier (thread-safe).
    获取或创建单例 IntentClassifier（线程安全）。
    """
    if not hasattr(get_intent_classifier, "_instance"):
        with _lock:
            if not hasattr(get_intent_classifier, "_instance"):
                from agents.intent_classifier import IntentClassifier
                from agents.orchestrator import TOOL_KEYWORDS
                from skills.base_skill import discover_skills

                # Build skill trigger map
                skill_triggers = {}
                for name, meta in discover_skills().items():
                    skill_triggers[name] = meta.trigger_phrases

                # Capability keywords for registry-based routing
                capability_keywords = {
                    "code_review": ["代码审查", "code review", "review code"],
                    "test_generation": ["生成测试", "generate test", "test generation"],
                    "domain_qa": ["知识问答", "domain question", "knowledge query"],
                    "rl_dispatch": ["强化学习调度", "rl dispatch", "reinforcement"],
                    "report_generation": ["生成报告", "generate report", "report"],
                    "content_planning": ["内容规划", "content plan", "写作计划"],
                    "content_review": ["内容审核", "content review", "文章审查"],
                    "content_publish": ["内容发布", "publish content", "发布文章"],
                }

                get_intent_classifier._instance = IntentClassifier(
                    skill_triggers=skill_triggers,
                    tool_keywords=dict(TOOL_KEYWORDS),
                    capability_keywords=capability_keywords,
                )
    return get_intent_classifier._instance


def get_adaptive_scheduler():
    """Get or create the singleton AdaptiveScheduler (thread-safe).
    获取或创建单例 AdaptiveScheduler（线程安全）。
    """
    if not hasattr(get_adaptive_scheduler, "_instance"):
        with _lock:
            if not hasattr(get_adaptive_scheduler, "_instance"):
                from agents.adaptive_scheduler import AdaptiveScheduler
                get_adaptive_scheduler._instance = AdaptiveScheduler()
    return get_adaptive_scheduler._instance
