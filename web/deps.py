"""Shared web-layer singletons and dependencies.
Web 层共享的单例与依赖注入。
"""

from __future__ import annotations


def get_orchestrator():
    """Get or create the singleton OrchestratorAgent."""
    if not hasattr(get_orchestrator, "_instance"):
        from agents.orchestrator import OrchestratorAgent
        get_orchestrator._instance = OrchestratorAgent()
    return get_orchestrator._instance


def get_report_agent():
    """Get or create the singleton ReportAgent."""
    if not hasattr(get_report_agent, "_instance"):
        from agents.report_agent import ReportAgent
        get_report_agent._instance = ReportAgent()
    return get_report_agent._instance
