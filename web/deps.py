"""Shared web-layer singletons and dependencies.
Web 层共享的单例与依赖注入。
"""

from __future__ import annotations

import threading

_lock = threading.RLock()


def get_orchestrator():
    """Get or create the singleton OrchestratorAgent (thread-safe).
    Wired with registry, health monitor, and message bus for full routing.
    """
    if not hasattr(get_orchestrator, "_instance"):
        with _lock:
            if not hasattr(get_orchestrator, "_instance"):
                from agents.orchestrator import OrchestratorAgent
                get_orchestrator._instance = OrchestratorAgent(
                    agent_id="orchestrator",
                    registry=get_agent_registry(),
                    health_monitor=get_health_monitor(),
                    message_bus=get_message_bus(),
                )
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
                    DailyReportSkill, CollaborativeDevSkill,
                )
                from openclaw.skills.content_pipeline_skill import ContentPipelineSkill

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
                    "collaborative_dev": CollaborativeDevSkill,
                    "content_pipeline": ContentPipelineSkill,
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


def get_feishu_client():
    """Get or create the singleton FeishuClient (thread-safe).
    获取或创建单例 FeishuClient（线程安全）。
    """
    if not hasattr(get_feishu_client, "_instance"):
        with _lock:
            if not hasattr(get_feishu_client, "_instance"):
                import os
                from integrations.feishu_client import FeishuClient
                get_feishu_client._instance = FeishuClient(
                    app_id=os.environ.get("FEISHU_APP_ID", ""),
                    app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
                    verification_token=os.environ.get("FEISHU_VERIFICATION_TOKEN", ""),
                    encrypt_key=os.environ.get("FEISHU_ENCRYPT_KEY", ""),
                )
    return get_feishu_client._instance


def get_feishu_bot():
    """Get or create the singleton FeishuBotHandler (thread-safe).
    获取或创建单例 FeishuBotHandler（线程安全）。
    """
    if not hasattr(get_feishu_bot, "_instance"):
        with _lock:
            if not hasattr(get_feishu_bot, "_instance"):
                import os
                from integrations.feishu_bot import FeishuBotHandler
                # Parse user→role mapping: "uid1:admin,uid2:researcher"
                user_roles = {}
                roles_env = os.environ.get("FEISHU_USER_ROLES", "")
                if roles_env:
                    for pair in roles_env.split(","):
                        parts = pair.strip().split(":")
                        if len(parts) == 2:
                            user_roles[parts[0].strip()] = parts[1].strip()

                get_feishu_bot._instance = FeishuBotHandler(
                    app_id=os.environ.get("FEISHU_APP_ID", ""),
                    app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
                    webhook_url=os.environ.get("FEISHU_WEBHOOK_URL", ""),
                    client=get_feishu_client(),
                    user_roles=user_roles,
                    rate_limit=int(os.environ.get("FEISHU_RATE_LIMIT", "5")),
                )
    return get_feishu_bot._instance


def get_feishu_alert():
    """Get or create the singleton FeishuAlertSender (thread-safe).
    获取或创建单例 FeishuAlertSender（线程安全）。
    """
    if not hasattr(get_feishu_alert, "_instance"):
        with _lock:
            if not hasattr(get_feishu_alert, "_instance"):
                import os
                from integrations.feishu_alert import FeishuAlertSender
                get_feishu_alert._instance = FeishuAlertSender(
                    webhook_url=os.environ.get("FEISHU_ALERT_WEBHOOK_URL", ""),
                    client=get_feishu_client(),
                )
    return get_feishu_alert._instance


def get_feishu_sync():
    """Get or create the singleton FeishuBitableSync (thread-safe).
    获取或创建单例 FeishuBitableSync（线程安全）。
    """
    if not hasattr(get_feishu_sync, "_instance"):
        with _lock:
            if not hasattr(get_feishu_sync, "_instance"):
                import os
                from integrations.feishu_sync import FeishuBitableSync
                get_feishu_sync._instance = FeishuBitableSync(
                    app_token=os.environ.get("FEISHU_BITABLE_APP_TOKEN", ""),
                    client=get_feishu_client(),
                )
    return get_feishu_sync._instance


# ---------------------------------------------------------------------------
# HydroClaw workbench singletons (v0.2.0)
# ---------------------------------------------------------------------------

def get_rbac():
    """Get or create the singleton RBACManager (thread-safe).
    获取或创建 RBAC 权限管理器单例（线程安全）。
    """
    if not hasattr(get_rbac, "_instance"):
        with _lock:
            if not hasattr(get_rbac, "_instance"):
                from hydroclaw.rbac import RBACManager
                get_rbac._instance = RBACManager()
    return get_rbac._instance


def get_session_mgr():
    """Get or create the singleton SessionManager (thread-safe).
    获取或创建会话管理器单例（线程安全）。
    """
    if not hasattr(get_session_mgr, "_instance"):
        with _lock:
            if not hasattr(get_session_mgr, "_instance"):
                from hydroclaw.session import SessionManager
                get_session_mgr._instance = SessionManager()
    return get_session_mgr._instance


def get_interaction_logger():
    """Get or create the singleton InteractionLogger (thread-safe).
    获取或创建交互日志记录器单例（线程安全）。
    """
    if not hasattr(get_interaction_logger, "_instance"):
        with _lock:
            if not hasattr(get_interaction_logger, "_instance"):
                from hydroclaw.evolution.logger import InteractionLogger
                get_interaction_logger._instance = InteractionLogger()
    return get_interaction_logger._instance


def get_memory_mgr():
    """Get or create the singleton MemoryManager (thread-safe).
    获取或创建记忆管理器单例（线程安全）。
    """
    if not hasattr(get_memory_mgr, "_instance"):
        with _lock:
            if not hasattr(get_memory_mgr, "_instance"):
                from hydroclaw.memory import MemoryManager
                get_memory_mgr._instance = MemoryManager()
    return get_memory_mgr._instance


def get_personality_mgr():
    """Get or create the singleton PersonalityManager (thread-safe).
    获取或创建人格管理器单例（线程安全）。
    """
    if not hasattr(get_personality_mgr, "_instance"):
        with _lock:
            if not hasattr(get_personality_mgr, "_instance"):
                from hydroclaw.personality import PersonalityManager
                get_personality_mgr._instance = PersonalityManager()
    return get_personality_mgr._instance


def get_heartbeat():
    """Get or create the singleton HeartbeatService (thread-safe).
    获取或创建心跳服务单例（线程安全）。
    """
    if not hasattr(get_heartbeat, "_instance"):
        with _lock:
            if not hasattr(get_heartbeat, "_instance"):
                from hydroclaw.heartbeat import HeartbeatService
                get_heartbeat._instance = HeartbeatService()
    return get_heartbeat._instance


def get_evolution_analyzer():
    """Get or create the singleton EvolutionAnalyzer (thread-safe).
    获取或创建进化分析器单例（线程安全）。
    """
    if not hasattr(get_evolution_analyzer, "_instance"):
        with _lock:
            if not hasattr(get_evolution_analyzer, "_instance"):
                from hydroclaw.evolution.analyzer import EvolutionAnalyzer
                get_evolution_analyzer._instance = EvolutionAnalyzer()
    return get_evolution_analyzer._instance
