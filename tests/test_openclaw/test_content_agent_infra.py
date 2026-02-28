"""Tests for OpenClaw content agent BaseAgent integration.

验证 OpenClaw 内容 Agent 正确继承 BaseAgent，支持消息处理、
能力查询和 MessageBus/Registry 集成。
"""

from __future__ import annotations

import asyncio

import pytest

from agents.base_agent import AgentCard, AgentStatus, BaseAgent
from agents.message import AgentMessage, MessageBus, MessageType
from agents.registry import AgentRegistry


# ---------------------------------------------------------------------------
# BaseAgent inheritance
# ---------------------------------------------------------------------------

class TestContentAgentInheritance:
    """Verify all OpenClaw content agents inherit from BaseAgent."""

    def test_content_planner_is_base_agent(self):
        from openclaw.agents.content_planner import ContentPlannerAgent
        agent = ContentPlannerAgent()
        assert isinstance(agent, BaseAgent)
        assert "requirement_analysis" in agent.get_capabilities()
        assert "outline_generation" in agent.get_capabilities()

    def test_content_reviewer_is_base_agent(self):
        from openclaw.agents.content_reviewer import ContentReviewerAgent
        agent = ContentReviewerAgent()
        assert isinstance(agent, BaseAgent)
        assert "structure_review" in agent.get_capabilities()
        assert "compliance_review" in agent.get_capabilities()

    def test_content_publisher_is_base_agent(self):
        from openclaw.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        assert isinstance(agent, BaseAgent)
        assert "feishu_publish" in agent.get_capabilities()
        assert "wechat_publish" in agent.get_capabilities()

    def test_content_orchestrator_is_base_agent(self):
        from openclaw.agents.content_orchestrator import ContentOrchestratorAgent
        agent = ContentOrchestratorAgent()
        assert isinstance(agent, BaseAgent)
        assert "full_pipeline" in agent.get_capabilities()
        assert "plan_only" in agent.get_capabilities()

    def test_all_content_agents_have_agent_id(self):
        from openclaw.agents.content_planner import ContentPlannerAgent
        from openclaw.agents.content_reviewer import ContentReviewerAgent
        from openclaw.agents.content_publisher import ContentPublisherAgent
        from openclaw.agents.content_orchestrator import ContentOrchestratorAgent

        for cls in [ContentPlannerAgent, ContentReviewerAgent,
                    ContentPublisherAgent, ContentOrchestratorAgent]:
            agent = cls()
            assert agent.agent_id is not None
            assert agent.status == AgentStatus.IDLE

    def test_custom_agent_id(self):
        from openclaw.agents.content_planner import ContentPlannerAgent
        agent = ContentPlannerAgent(agent_id="my_planner")
        assert agent.agent_id == "my_planner"


# ---------------------------------------------------------------------------
# Message handling
# ---------------------------------------------------------------------------

class TestContentPlannerMessages:
    """Test ContentPlannerAgent handle_message dispatch."""

    def setup_method(self):
        from openclaw.agents.content_planner import ContentPlannerAgent
        self.agent = ContentPlannerAgent(agent_id="planner")

    def test_plan_action(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="planner",
            content={"action": "plan", "text": "写一篇关于水网的技术文章"},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert "result" in resp.content
        assert "plan_id" in resp.content["result"]

    def test_analyse_requirement_action(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="planner",
            content={"action": "analyse_requirement", "text": "写一篇教程"},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert resp.content["result"]["content_type"] == "tutorial"

    def test_default_action_is_plan(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="planner",
            content={"text": "写一篇报告"},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert "plan_id" in resp.content["result"]


class TestContentReviewerMessages:
    """Test ContentReviewerAgent handle_message dispatch."""

    def setup_method(self):
        from openclaw.agents.content_reviewer import ContentReviewerAgent
        self.agent = ContentReviewerAgent(agent_id="reviewer")

    def test_review_article(self):
        article = "# Title\n\n## Section 1\n\nContent here with enough text to pass.\n\n## Section 2\n\nMore content for the article that is long enough."
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="reviewer",
            content={"action": "review_article", "content": article},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert "score" in resp.content["result"]

    def test_review_image_config(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="reviewer",
            content={
                "action": "review_image_config",
                "config": {"images": [{"prompt": "A beautiful water network diagram showing pipes", "filename": "img1.png"}]},
            },
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert resp.content["result"]["passed"] is True

    def test_unknown_action(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="reviewer",
            content={"action": "unknown_action"},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.ERROR


class TestContentPublisherMessages:
    """Test ContentPublisherAgent handle_message dispatch."""

    def setup_method(self):
        from openclaw.agents.content_publisher import ContentPublisherAgent
        self.agent = ContentPublisherAgent(agent_id="publisher")

    def test_plan_publish(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="publisher",
            content={"action": "plan_publish", "channels": ["feishu", "wechat"]},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert isinstance(resp.content["result"], list)

    def test_get_history(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="publisher",
            content={"action": "get_history"},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert isinstance(resp.content["result"], list)

    def test_unknown_action(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="publisher",
            content={"action": "nonexistent"},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.ERROR


class TestContentOrchestratorMessages:
    """Test ContentOrchestratorAgent handle_message dispatch."""

    def setup_method(self):
        from openclaw.agents.content_orchestrator import ContentOrchestratorAgent
        self.agent = ContentOrchestratorAgent(agent_id="orchestrator")

    def test_plan_only(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="orchestrator",
            content={"action": "plan_only", "requirement": "写一篇AI文章"},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert "plan_id" in resp.content["result"]

    def test_review_only(self):
        article = "# Test\n\n## Intro\n\nContent section.\n\n## End\n\nConclusion."
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="orchestrator",
            content={"action": "review_only", "content": article},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert "score" in resp.content["result"]

    def test_run_full_pipeline(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="orchestrator",
            content={
                "action": "run_full_pipeline",
                "requirement": "写一篇技术文章",
                "channels": ["feishu"],
            },
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.RESPONSE
        assert resp.content["result"]["success"] is True

    def test_unknown_action(self):
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="orchestrator",
            content={"action": "bad_action"},
        )
        resp = asyncio.get_event_loop().run_until_complete(
            self.agent.handle_message(msg),
        )
        assert resp.type == MessageType.ERROR


# ---------------------------------------------------------------------------
# Registry & MessageBus integration
# ---------------------------------------------------------------------------

class TestContentAgentRegistryIntegration:
    """Test that content agents work with the multi-agent registry."""

    def test_register_all_content_agents(self):
        from openclaw.agents.content_planner import ContentPlannerAgent
        from openclaw.agents.content_reviewer import ContentReviewerAgent
        from openclaw.agents.content_publisher import ContentPublisherAgent
        from openclaw.agents.content_orchestrator import ContentOrchestratorAgent

        registry = AgentRegistry()
        planner = ContentPlannerAgent(agent_id="cp")
        reviewer = ContentReviewerAgent(agent_id="cr")
        publisher = ContentPublisherAgent(agent_id="pub")
        orch = ContentOrchestratorAgent(agent_id="co")

        for agent in [planner, reviewer, publisher, orch]:
            registry.register(agent)

        assert len(registry.get_all_agents()) == 4

    def test_find_by_capability(self):
        from openclaw.agents.content_planner import ContentPlannerAgent
        from openclaw.agents.content_reviewer import ContentReviewerAgent

        registry = AgentRegistry()
        registry.register(ContentPlannerAgent(agent_id="cp"))
        registry.register(ContentReviewerAgent(agent_id="cr"))

        found = registry.find_by_capability("outline_generation")
        assert len(found) == 1
        assert found[0].agent_id == "cp"

        found = registry.find_by_capability("compliance_review")
        assert len(found) == 1
        assert found[0].agent_id == "cr"

    def test_bus_integration(self):
        from openclaw.agents.content_planner import ContentPlannerAgent

        registry = AgentRegistry()
        bus = MessageBus()
        registry.connect_bus(bus)

        planner = ContentPlannerAgent(agent_id="cp")
        registry.register(planner)

        # Bus should have a handler for "cp"
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="test",
            recipient="cp",
            content={"text": "写一篇文章"},
        )
        resp = asyncio.get_event_loop().run_until_complete(bus.send(msg))
        assert resp is not None
        assert resp.type == MessageType.RESPONSE
        assert "result" in resp.content

    def test_lifecycle(self):
        from openclaw.agents.content_planner import ContentPlannerAgent

        agent = ContentPlannerAgent(agent_id="cp")
        assert agent.status == AgentStatus.IDLE

        asyncio.get_event_loop().run_until_complete(agent.initialize())
        assert agent.status == AgentStatus.IDLE

        asyncio.get_event_loop().run_until_complete(agent.shutdown())
        assert agent.status == AgentStatus.STOPPED

    def test_summary_includes_content_agents(self):
        from openclaw.agents.content_planner import ContentPlannerAgent
        from openclaw.agents.content_reviewer import ContentReviewerAgent
        from openclaw.agents.content_publisher import ContentPublisherAgent
        from openclaw.agents.content_orchestrator import ContentOrchestratorAgent

        registry = AgentRegistry()
        registry.register(ContentPlannerAgent(agent_id="cp"))
        registry.register(ContentReviewerAgent(agent_id="cr"))
        registry.register(ContentPublisherAgent(agent_id="pub"))
        registry.register(ContentOrchestratorAgent(agent_id="co"))

        summary = registry.summary()
        assert summary["total_agents"] == 4
        # All agents are idle
        assert all(a["status"] == "idle" for a in summary["agents"])
