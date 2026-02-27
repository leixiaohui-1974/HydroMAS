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
