"""HydroOS Agents — L4 flexible multi-agent orchestration.
HydroOS 智能体层 — L4 灵活多智能体编排。

Agents are the top-level decision makers that select Skills,
Tools, and sub-Agents based on user intent.

Multi-agent infrastructure:
    - BaseAgent: Abstract base class for all agents
    - AgentMessage / MessageBus: Inter-agent communication protocol
    - AgentRegistry: Central agent discovery and management
    - AgentContext: Shared blackboard for collaboration state
    - MultiAgentExecutor: DAG-based collaborative task execution
"""

# Multi-agent infrastructure
from agents.base_agent import AgentCard, AgentStatus, BaseAgent
from agents.context import AgentContext, TraceEntry
from agents.executor import (
    ExecutionPlan,
    ExecutionTask,
    MultiAgentExecutor,
    TaskStatus,
)
from agents.message import (
    AgentMessage,
    MessageBus,
    MessagePriority,
    MessageType,
)
from agents.registry import AgentRegistry

# Domain agents
from agents.analysis_agent import AnalysisAgent
from agents.dev_orchestrator import DevOrchestratorAgent
from agents.dev_planner import DevPlannerAgent
from agents.dev_reviewer import DevReviewerAgent
from agents.dev_tester import DevTesterAgent
from agents.handuo_agent import HanduoAgent
from agents.orchestrator import TOOL_KEYWORDS, OrchestratorAgent
from agents.planning_agent import PlanningAgent, TaskNode, TaskPlan
from agents.report_agent import ReportAgent
from agents.rl_dispatch_agent import DispatchAction, DispatchState, RLDispatchAgent
from agents.safety_agent import SafetyAgent

__all__ = [
    # Multi-agent infrastructure
    "BaseAgent",
    "AgentCard",
    "AgentStatus",
    "AgentMessage",
    "MessageType",
    "MessagePriority",
    "MessageBus",
    "AgentRegistry",
    "AgentContext",
    "TraceEntry",
    "MultiAgentExecutor",
    "ExecutionPlan",
    "ExecutionTask",
    "TaskStatus",
    # Domain agents
    "OrchestratorAgent",
    "TOOL_KEYWORDS",
    "TaskNode",
    "TaskPlan",
    "PlanningAgent",
    "AnalysisAgent",
    "ReportAgent",
    "SafetyAgent",
    "HanduoAgent",
    "DispatchState",
    "DispatchAction",
    "RLDispatchAgent",
    # DevOps agents
    "DevPlannerAgent",
    "DevReviewerAgent",
    "DevTesterAgent",
    "DevOrchestratorAgent",
]
