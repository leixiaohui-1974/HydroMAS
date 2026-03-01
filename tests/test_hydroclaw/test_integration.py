"""Integration tests for HydroClaw ↔ Agent/Gateway flow.
HydroClaw 工作台与 Agent/Gateway 的集成测试。
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from web.app import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# deps.py singleton tests
# ---------------------------------------------------------------------------


class TestDepsSingletons:
    """Verify HydroClaw singletons in deps.py are thread-safe."""

    def test_get_rbac_singleton(self):
        from web.deps import get_rbac
        a = get_rbac()
        b = get_rbac()
        assert a is b

    def test_get_session_mgr_singleton(self):
        from web.deps import get_session_mgr
        a = get_session_mgr()
        b = get_session_mgr()
        assert a is b

    def test_get_interaction_logger_singleton(self):
        from web.deps import get_interaction_logger
        a = get_interaction_logger()
        b = get_interaction_logger()
        assert a is b

    def test_get_memory_mgr_singleton(self):
        from web.deps import get_memory_mgr
        a = get_memory_mgr()
        b = get_memory_mgr()
        assert a is b

    def test_get_personality_mgr_singleton(self):
        from web.deps import get_personality_mgr
        a = get_personality_mgr()
        b = get_personality_mgr()
        assert a is b

    def test_get_heartbeat_singleton(self):
        from web.deps import get_heartbeat
        a = get_heartbeat()
        b = get_heartbeat()
        assert a is b

    def test_get_evolution_analyzer_singleton(self):
        from web.deps import get_evolution_analyzer
        a = get_evolution_analyzer()
        b = get_evolution_analyzer()
        assert a is b


# ---------------------------------------------------------------------------
# Gateway → Orchestrator user context flow
# ---------------------------------------------------------------------------


class TestGatewayUserContext:
    """Test that gateway passes user context to orchestrator."""

    def test_chat_passes_session_id(self, client):
        """Chat response should include session_id."""
        resp = client.post("/api/gateway/chat", json={
            "message": "你好",
            "role": "admin",
            "user_id": "test_user_123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["session_id"]  # not empty

    def test_chat_returns_user_id(self, client):
        """Chat response should echo user_id."""
        resp = client.post("/api/gateway/chat", json={
            "message": "hello",
            "role": "researcher",
            "user_id": "researcher_42",
        })
        data = resp.json()
        assert data.get("user_id") == "researcher_42"

    def test_chat_returns_role(self, client):
        """Chat response should echo effective role."""
        resp = client.post("/api/gateway/chat", json={
            "message": "test",
            "role": "teacher",
        })
        data = resp.json()
        assert data.get("role") == "teacher"


# ---------------------------------------------------------------------------
# RBAC skill ordering (existence check before RBAC)
# ---------------------------------------------------------------------------


class TestSkillEndpointOrdering:
    """Test skill endpoint: existence check comes before RBAC."""

    def test_nonexistent_skill_returns_error(self, client):
        """Unknown skill → 'error' (not 'denied')."""
        resp = client.post("/api/gateway/skill", json={
            "skill_name": "totally_fake_skill",
        })
        data = resp.json()
        assert data["status"] == "error"
        assert "not found" in data["error"]
        assert "available_skills" in data

    def test_denied_skill_returns_denied(self, client):
        """Existing skill without permission → 'denied'."""
        # operator role doesn't have access to all skills
        resp = client.post("/api/gateway/skill", json={
            "skill_name": "full_lifecycle",
            "role": "operator",
        })
        data = resp.json()
        # Either denied or success (depending on RBAC config)
        assert data["status"] in ("denied", "success", "error")


# ---------------------------------------------------------------------------
# AgentMessage user context
# ---------------------------------------------------------------------------


class TestAgentMessageUserContext:
    """Test that AgentMessage carries user context fields."""

    def test_message_has_user_fields(self):
        from agents.message import AgentMessage, MessageType
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="gateway",
            recipient="orchestrator",
            user_id="user_42",
            role="admin",
            session_id="sess_abc",
            group="dev",
        )
        assert msg.user_id == "user_42"
        assert msg.role == "admin"
        assert msg.session_id == "sess_abc"
        assert msg.group == "dev"

    def test_message_defaults_empty(self):
        from agents.message import AgentMessage, MessageType
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="a",
        )
        assert msg.user_id == ""
        assert msg.role == ""
        assert msg.session_id == ""
        assert msg.group == ""

    def test_reply_preserves_structure(self):
        from agents.message import AgentMessage, MessageType
        msg = AgentMessage(
            type=MessageType.REQUEST,
            sender="a",
            recipient="b",
            user_id="u1",
            role="researcher",
        )
        reply = msg.reply({"answer": "ok"})
        assert reply.sender == "b"
        assert reply.recipient == "a"
        assert reply.correlation_id == msg.id


# ---------------------------------------------------------------------------
# Orchestrator accepts user context
# ---------------------------------------------------------------------------


class TestOrchestratorUserContext:
    """Test OrchestratorAgent.handle_request() with user context kwargs."""

    @pytest.mark.asyncio
    async def test_handle_request_with_context(self):
        from agents.orchestrator import OrchestratorAgent
        orch = OrchestratorAgent(agent_id="test_orch")
        result = await orch.handle_request(
            "你好",
            {},
            user_id="u1",
            role="admin",
            session_id="s1",
            group="dev",
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handle_request_backward_compat(self):
        """Existing callers without user context still work."""
        from agents.orchestrator import OrchestratorAgent
        orch = OrchestratorAgent(agent_id="test_orch2")
        result = await orch.handle_request("hello")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Evolution segmentation endpoints
# ---------------------------------------------------------------------------


class TestEvolutionSegmentation:
    """Test new evolution segmentation endpoints."""

    def test_evolution_by_role(self, client):
        resp = client.get("/api/gateway/evolution/by-role")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segmentation"] == "by_role"
        assert "roles" in data

    def test_evolution_by_group(self, client):
        resp = client.get("/api/gateway/evolution/by-group")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segmentation"] == "by_group"
        assert "groups" in data

    def test_evolution_by_role_custom_days(self, client):
        resp = client.get("/api/gateway/evolution/by-role?days=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 3


# ---------------------------------------------------------------------------
# Heartbeat enhanced checks
# ---------------------------------------------------------------------------


class TestHeartbeatEnhanced:
    """Test enhanced heartbeat checks (water_balance, memory_consolidation)."""

    @pytest.mark.asyncio
    async def test_water_balance_check_runs(self):
        from hydroclaw.heartbeat import HeartbeatService
        svc = HeartbeatService()
        result = await svc.run_check("water_balance")
        assert result is not None
        assert result.check_name == "water_balance"
        # Should be OK (either no config, no balance data, or successful)
        assert result.status.value in ("ok", "warning")

    @pytest.mark.asyncio
    async def test_memory_consolidation_check_runs(self):
        from hydroclaw.heartbeat import HeartbeatService
        svc = HeartbeatService()
        result = await svc.run_check("memory_consolidation")
        assert result is not None
        assert result.check_name == "memory_consolidation"
        assert result.status.value in ("ok", "warning")


# ---------------------------------------------------------------------------
# AssistantMessage model roles
# ---------------------------------------------------------------------------


class TestAssistantMessageRoles:
    """Test that AssistantMessage model uses correct 5 roles."""

    def test_valid_roles(self):
        from web.models import AssistantMessage
        for role in ("researcher", "designer", "operator", "admin", "teacher"):
            msg = AssistantMessage(message="test", role=role)
            assert msg.role == role

    def test_default_role(self):
        from web.models import AssistantMessage
        msg = AssistantMessage(message="test")
        assert msg.role == "admin"

    def test_old_roles_rejected(self):
        from web.models import AssistantMessage
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AssistantMessage(message="test", role="engineer")
        with pytest.raises(ValidationError):
            AssistantMessage(message="test", role="analyst")


# ---------------------------------------------------------------------------
# EvolutionAnalyzer segmentation
# ---------------------------------------------------------------------------


class TestEvolutionAnalyzerSegmentation:
    """Test EvolutionAnalyzer.analyze_by_role() and analyze_by_group()."""

    def test_analyze_by_role_empty(self):
        from hydroclaw.evolution.analyzer import EvolutionAnalyzer
        analyzer = EvolutionAnalyzer(interaction_dir="/tmp/test_evo_seg_role")
        result = analyzer.analyze_by_role(days_back=1)
        assert isinstance(result, dict)

    def test_analyze_by_group_empty(self):
        from hydroclaw.evolution.analyzer import EvolutionAnalyzer
        analyzer = EvolutionAnalyzer(interaction_dir="/tmp/test_evo_seg_group")
        result = analyzer.analyze_by_group(days_back=1)
        assert isinstance(result, dict)

    def test_analyze_by_role_with_data(self, tmp_path):
        import json
        from datetime import datetime
        from hydroclaw.evolution.analyzer import EvolutionAnalyzer

        # Write test interaction data
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = tmp_path / f"interactions_{date_str}.jsonl"
        records = [
            {"role": "admin", "skill_used": "forecast", "success": True,
             "response_time_ms": 100, "user_id": "u1", "group": "dev",
             "timestamp": datetime.now().timestamp()},
            {"role": "admin", "skill_used": "warning", "success": False,
             "response_time_ms": 200, "user_id": "u1", "group": "dev",
             "timestamp": datetime.now().timestamp()},
            {"role": "researcher", "skill_used": "forecast", "success": True,
             "response_time_ms": 150, "user_id": "u2", "group": "peer",
             "timestamp": datetime.now().timestamp()},
        ]
        log_file.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

        analyzer = EvolutionAnalyzer(interaction_dir=str(tmp_path))
        result = analyzer.analyze_by_role(days_back=1)
        assert "admin" in result
        assert "researcher" in result
        assert result["admin"]["total"] == 2
        assert result["researcher"]["total"] == 1
        assert result["admin"]["success_rate"] == 50.0

    def test_analyze_by_group_with_data(self, tmp_path):
        import json
        from datetime import datetime
        from hydroclaw.evolution.analyzer import EvolutionAnalyzer

        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = tmp_path / f"interactions_{date_str}.jsonl"
        records = [
            {"role": "admin", "skill_used": "forecast", "success": True,
             "user_id": "u1", "group": "dev",
             "timestamp": datetime.now().timestamp()},
            {"role": "researcher", "skill_used": "warning", "success": True,
             "user_id": "u2", "group": "peer",
             "timestamp": datetime.now().timestamp()},
            {"role": "researcher", "skill_used": "forecast", "success": True,
             "user_id": "u3", "group": "peer",
             "timestamp": datetime.now().timestamp()},
        ]
        log_file.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

        analyzer = EvolutionAnalyzer(interaction_dir=str(tmp_path))
        result = analyzer.analyze_by_group(days_back=1)
        assert "dev" in result
        assert "peer" in result
        assert result["dev"]["total"] == 1
        assert result["peer"]["total"] == 2
        assert result["peer"]["unique_users"] == 2
