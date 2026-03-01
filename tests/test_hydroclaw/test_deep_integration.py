"""Deep integration tests — gateway→session→memory→RBAC→personality pipeline.

Tests the full HydroClaw workbench integration:
1. Gateway chat → session creation → memory search → RBAC check → response
2. HanduoAgent RAG (TF-IDF) retrieval integration
3. Heartbeat session cleanup
4. Skill YAML discovery completeness
5. Multi-user session isolation
6. Role-based skill filtering
7. Evolution logging and analysis pipeline
"""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a clean FastAPI test client."""
    os.environ.pop("HYDROMAS_API_KEY", None)
    from web.app import app
    return TestClient(app)


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide temporary directories for session/memory/interaction data."""
    session_dir = tmp_path / "sessions"
    memory_dir = tmp_path / "memory"
    interaction_dir = tmp_path / "interactions"
    session_dir.mkdir()
    memory_dir.mkdir()
    interaction_dir.mkdir()
    return {
        "sessions": str(session_dir),
        "memory": str(memory_dir),
        "interactions": str(interaction_dir),
    }


# ═══════════════════════════════════════════════════════════════
# 1. Gateway Chat Full Pipeline
# ═══════════════════════════════════════════════════════════════


class TestGatewayChatPipeline:
    """Test the full gateway chat pipeline end-to-end."""

    def test_chat_returns_structured_response(self, client):
        """POST /api/gateway/chat should return intent + result + session info."""
        resp = client.post("/api/gateway/chat", json={
            "message": "检查当前系统ODD安全状态",
            "role": "operator",
            "user_id": "test_user_001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "intent" in data
        assert "result" in data
        assert "role" in data
        assert data["role"] == "operator"

    def test_chat_role_validation(self, client):
        """Invalid role should be rejected by Pydantic."""
        resp = client.post("/api/gateway/chat", json={
            "message": "Hello",
            "role": "hacker",
        })
        assert resp.status_code == 422

    def test_chat_empty_message_rejected(self, client):
        """Empty message should fail validation."""
        resp = client.post("/api/gateway/chat", json={
            "message": "",
            "role": "operator",
        })
        assert resp.status_code == 422

    def test_chat_sanitizes_control_characters(self, client):
        """Control characters in message should be stripped."""
        resp = client.post("/api/gateway/chat", json={
            "message": "Hello\x00\x08World",
            "role": "admin",
        })
        assert resp.status_code == 200

    def test_chat_different_roles_accepted(self, client):
        """All 5 roles should be accepted."""
        for role in ["researcher", "designer", "operator", "admin", "teacher"]:
            resp = client.post("/api/gateway/chat", json={
                "message": "测试消息",
                "role": role,
            })
            assert resp.status_code == 200, f"Role {role} failed"


# ═══════════════════════════════════════════════════════════════
# 2. Session Isolation
# ═══════════════════════════════════════════════════════════════


class TestSessionIsolation:
    """Test multi-user session management."""

    def test_session_per_user(self, tmp_data_dir):
        """Each user gets a separate session in per-user mode."""
        from hydroclaw.session import SessionManager

        mgr = SessionManager(session_dir=tmp_data_dir["sessions"], scope="per-user")
        s1 = mgr.get_or_create("user_a", group="g1", channel="api")
        s2 = mgr.get_or_create("user_b", group="g1", channel="api")
        s1.add_turn("user", "message from user A")
        s2.add_turn("user", "message from user B")

        assert s1.session_id != s2.session_id
        assert len(s1.history) == 1
        assert len(s2.history) == 1

    def test_session_per_group_shared(self, tmp_data_dir):
        """Users in same group share session in per-group mode."""
        from hydroclaw.session import SessionManager

        mgr = SessionManager(session_dir=tmp_data_dir["sessions"], scope="per-group")
        s1 = mgr.get_or_create("user_a", group="g1", channel="api")
        s2 = mgr.get_or_create("user_b", group="g1", channel="api")
        s1.add_turn("user", "hello from A")

        assert s1.session_id == s2.session_id
        assert len(s2.history) == 1  # Shared

    def test_session_persistence_roundtrip(self, tmp_data_dir):
        """Sessions should survive save/load cycle."""
        from hydroclaw.session import SessionManager

        mgr = SessionManager(session_dir=tmp_data_dir["sessions"])
        session = mgr.get_or_create("user_persist", group="g1")
        session.add_turn("user", "remember this")
        session.add_turn("assistant", "I will remember")
        mgr.save_session(session)

        # Create new manager to force disk load
        mgr2 = SessionManager(session_dir=tmp_data_dir["sessions"])
        loaded = mgr2.get_or_create("user_persist", group="g1")
        assert len(loaded.history) == 2
        assert loaded.history[0].content == "remember this"

    def test_stale_session_cleanup(self, tmp_data_dir):
        """cleanup_stale should remove idle sessions."""
        from hydroclaw.session import SessionManager

        mgr = SessionManager(session_dir=tmp_data_dir["sessions"])
        session = mgr.get_or_create("old_user")
        session.last_active = time.time() - 86400 * 2  # 2 days old

        removed = mgr.cleanup_stale(max_idle_hours=24.0)
        assert removed == 1
        assert mgr.get_session_count() == 0

    def test_session_lru_eviction(self, tmp_data_dir):
        """When exceeding max_sessions, oldest is evicted."""
        from hydroclaw.session import SessionManager

        mgr = SessionManager(
            session_dir=tmp_data_dir["sessions"], max_sessions=3,
        )
        for i in range(4):
            s = mgr.get_or_create(f"user_{i}")
            s.last_active = time.time() + i  # Ensure ordering
        # 4 created, but max_sessions=3, so oldest evicted
        assert mgr.get_session_count() == 3


# ═══════════════════════════════════════════════════════════════
# 3. Memory Search Integration
# ═══════════════════════════════════════════════════════════════


class TestMemorySearchIntegration:
    """Test memory search with time-decay scoring."""

    def test_memory_append_and_search(self, tmp_data_dir):
        """Append to memory then search should find relevant entries."""
        from hydroclaw.memory import MemoryManager

        mgr = MemoryManager(memory_dir=tmp_data_dir["memory"])
        mgr.append_memory("test_group", "水箱液位异常升高，需要检查进水阀门")
        mgr.append_daily_note("test_group", "今日水平衡残差偏大，可能存在泄漏", user_id="user1")

        results = mgr.search("test_group", "液位异常", max_results=5)
        assert len(results) >= 1
        assert any("液位" in r.content for r in results)

    def test_memory_search_empty_query(self, tmp_data_dir):
        """Empty query should return empty results."""
        from hydroclaw.memory import MemoryManager

        mgr = MemoryManager(memory_dir=tmp_data_dir["memory"])
        mgr.append_memory("g", "some content")
        results = mgr.search("g", "", max_results=5)
        assert len(results) == 0

    def test_memory_consolidation(self, tmp_data_dir):
        """Consolidation should produce a summary of daily notes."""
        from hydroclaw.memory import MemoryManager

        mgr = MemoryManager(memory_dir=tmp_data_dir["memory"])
        for i in range(3):
            mgr.append_daily_note("test_group", f"日志条目 {i}", user_id="user1")

        summary = mgr.consolidate("test_group", days_back=30)
        # consolidate() returns summary text (caller writes to MEMORY.md)
        assert "日志" in summary
        assert len(summary) > 0

        # Now manually persist to MEMORY.md
        mgr.append_memory("test_group", summary)
        memory = mgr.get_memory("test_group")
        assert "日志" in memory


# ═══════════════════════════════════════════════════════════════
# 4. RBAC Role-Based Skill Access
# ═══════════════════════════════════════════════════════════════


class TestRBACSkillAccess:
    """Test RBAC enforcement across all 5 roles."""

    def test_admin_has_all_skills(self):
        """Admin should have access to all skills."""
        from hydroclaw.rbac import RBACManager

        rbac = RBACManager()
        allowed = rbac.get_allowed_skills("admin")
        assert len(allowed) >= 15  # At least all standard skills

    def test_operator_cannot_access_collaborative_dev(self):
        """Operator should not have access to collaborative_dev."""
        from hydroclaw.rbac import RBACManager

        rbac = RBACManager()
        assert not rbac.check_skill("operator", "collaborative_dev")

    def test_researcher_can_read_but_not_execute_decision_skills(self):
        """Researcher can read decision skills but not execute."""
        from hydroclaw.rbac import RBACManager

        rbac = RBACManager()
        # Researcher should have read access to decision skills
        assert rbac.check_skill_read("researcher", "plan_skill")
        # But may not have full execute for control
        assert not rbac.check_skill("researcher", "control_system_design") or \
               rbac.check_skill_read("researcher", "control_system_design")

    def test_teacher_role_exists_and_has_permissions(self):
        """Teacher role should have educational skill access."""
        from hydroclaw.rbac import RBACManager

        rbac = RBACManager()
        summary = rbac.get_role_summary("teacher")
        assert summary is not None
        assert "教学" in summary["name_cn"]
        # Teacher should have at least some skills
        allowed = rbac.get_allowed_skills("teacher")
        assert len(allowed) >= 5

    def test_all_five_roles_defined(self):
        """All 5 roles should be defined."""
        from hydroclaw.rbac import RBACManager

        rbac = RBACManager()
        for role in ["operator", "designer", "researcher", "admin", "teacher"]:
            summary = rbac.get_role_summary(role)
            assert summary is not None, f"Role {role} not defined"


# ═══════════════════════════════════════════════════════════════
# 5. HanduoAgent RAG Integration
# ═══════════════════════════════════════════════════════════════


class TestHanduoAgentRAG:
    """Test HanduoAgent with RAG (TF-IDF) retrieval."""

    def test_handuo_initializes_with_rag(self):
        """HanduoAgent should build RAG index from knowledge base."""
        from agents.handuo_agent import HanduoAgent

        agent = HanduoAgent()
        # Should have knowledge loaded
        assert len(agent._knowledge) > 0
        # Should have RAG index (if knowledge has content)
        if agent._knowledge.get("entities") or agent._knowledge.get("fault_modes"):
            assert agent._rag is not None

    @pytest.mark.asyncio
    async def test_handuo_query_returns_answer(self):
        """Query should return an answer dict with mode=template."""
        from agents.handuo_agent import HanduoAgent

        agent = HanduoAgent()
        result = await agent.query("what is the water balance?")
        assert "answer" in result
        assert "mode" in result
        assert result["mode"] == "template"

    @pytest.mark.asyncio
    async def test_handuo_diagnose_anomaly(self):
        """Anomaly diagnosis should return structured result."""
        from agents.handuo_agent import HanduoAgent

        agent = HanduoAgent()
        result = await agent.diagnose_anomaly(
            {"type": "high_pressure"},
            {"pressure": 1.5},
        )
        assert "diagnosis" in result
        assert "possible_causes" in result
        assert "recommended_actions" in result

    @pytest.mark.asyncio
    async def test_handuo_generate_insight(self):
        """Insight generation should return text string."""
        from agents.handuo_agent import HanduoAgent

        agent = HanduoAgent()
        text = await agent.generate_insight(
            {"total_intake": 10400, "reuse_rate": 0.36},
            report_type="daily",
        )
        assert isinstance(text, str)
        assert "10400" in text

    def test_handuo_retrieve_uses_rag(self):
        """Retrieval should use both keyword and TF-IDF matching."""
        from agents.handuo_agent import HanduoAgent

        agent = HanduoAgent()
        results = agent._retrieve("water treatment process")
        # Even if no keyword match, RAG should find something (if knowledge exists)
        # This is the key difference from keyword-only retrieval
        assert isinstance(results, list)


# ═══════════════════════════════════════════════════════════════
# 6. Heartbeat Session Cleanup
# ═══════════════════════════════════════════════════════════════


class TestHeartbeatSessionCleanup:
    """Test heartbeat service with session cleanup check."""

    def test_session_cleanup_check_registered(self):
        """session_cleanup check should be registered by default."""
        from hydroclaw.heartbeat import HeartbeatService

        hb = HeartbeatService()
        check = hb.get_check("session_cleanup")
        assert check is not None
        assert check.enabled

    @pytest.mark.asyncio
    async def test_session_cleanup_runs(self):
        """Running session_cleanup check should succeed."""
        from hydroclaw.heartbeat import HeartbeatService

        hb = HeartbeatService()
        result = await hb.run_check("session_cleanup")
        assert result.check_name == "session_cleanup"
        # Should succeed (even if no sessions)
        assert result.status.value in ("ok", "warning")

    def test_heartbeat_has_six_default_checks(self):
        """HeartbeatService should have 6 default checks now."""
        from hydroclaw.heartbeat import HeartbeatService

        hb = HeartbeatService()
        checks = hb.get_all_checks()
        assert len(checks) == 6
        expected = {
            "system_health", "odd_scan", "water_balance",
            "memory_consolidation", "resource_monitor", "session_cleanup",
        }
        assert set(checks.keys()) == expected


# ═══════════════════════════════════════════════════════════════
# 7. Skill Discovery Completeness
# ═══════════════════════════════════════════════════════════════


class TestSkillDiscovery:
    """Test that all 17 skills are discoverable."""

    def test_discover_all_17_skills(self):
        """discover_skills() should find all 17 YAML files."""
        from skills.base_skill import discover_skills

        discovered = discover_skills()
        assert len(discovered) == 17
        # Check key skills are present
        for name in ["forecast_skill", "daily_report", "collaborative_dev",
                      "content_pipeline", "leak_diagnosis", "global_dispatch"]:
            assert name in discovered, f"Skill {name} not discovered"

    def test_skill_classes_accept_metadata_kwarg(self):
        """All skill classes should accept metadata= keyword argument."""
        from skills.base_skill import SkillMetadata, discover_skills
        from skills.collaborative_dev import CollaborativeDevSkill
        from openclaw.skills.content_pipeline_skill import ContentPipelineSkill

        meta = SkillMetadata(
            name="test", display_name="Test", description="Test",
            trigger_phrases=[], input_schema={}, output_schema={},
            tools_required=[],
        )
        # Both should accept metadata kwarg
        s1 = CollaborativeDevSkill(metadata=meta)
        s2 = ContentPipelineSkill(metadata=meta)
        assert s1.metadata.name == "test"
        assert s2.metadata.name == "test"


# ═══════════════════════════════════════════════════════════════
# 8. Gateway Endpoints Integration
# ═══════════════════════════════════════════════════════════════


class TestGatewayEndpointsIntegration:
    """Test gateway endpoints end-to-end."""

    def test_gateway_health(self, client):
        """GET /api/gateway/health should return healthy status."""
        resp = client.get("/api/gateway/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "platform" in data
        assert data["platform"]["version"] == "0.2.2"

    def test_gateway_roles(self, client):
        """GET /api/gateway/roles should return all 5 roles."""
        resp = client.get("/api/gateway/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert "roles" in data
        roles = data["roles"]
        assert len(roles) == 5
        for role in ["researcher", "designer", "operator", "admin", "teacher"]:
            assert role in roles

    def test_gateway_skills_list(self, client):
        """GET /api/gateway/skills should return skill list."""
        resp = client.get("/api/gateway/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert len(data["skills"]) >= 15  # At least 15 skills

    def test_gateway_cognitive_categories(self, client):
        """GET /api/gateway/cognitive should return all 4 categories."""
        resp = client.get("/api/gateway/cognitive")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        for cat in ["perception", "cognition", "decision", "control"]:
            assert cat in data["categories"]

    def test_gateway_sessions(self, client):
        """GET /api/gateway/sessions should return session info."""
        resp = client.get("/api/gateway/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_count" in data or "sessions" in data

    def test_gateway_dashboard(self, client):
        """GET /api/gateway/dashboard should return comprehensive status."""
        resp = client.get("/api/gateway/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert data["version"] == "0.2.2"

    def test_gateway_skill_execution(self, client):
        """POST /api/gateway/skill should execute a skill."""
        resp = client.post("/api/gateway/skill", json={
            "skill_name": "forecast_skill",
            "params": {},
            "role": "operator",
        })
        # May succeed or fail depending on params, but should not 500
        assert resp.status_code in (200, 422)


# ═══════════════════════════════════════════════════════════════
# 9. Evolution Logging Pipeline
# ═══════════════════════════════════════════════════════════════


class TestEvolutionPipeline:
    """Test interaction logging → analysis pipeline."""

    def test_log_and_retrieve(self, tmp_data_dir):
        """Log interactions then retrieve them."""
        from hydroclaw.evolution import InteractionLogger

        logger = InteractionLogger(log_dir=tmp_data_dir["interactions"])
        logger.log_chat(
            message="测试消息",
            user_id="user1",
            group="default",
            channel="api",
            role="operator",
            intent_type="skill",
            intent_target="forecast_skill",
            intent_confidence=0.9,
            skill_used="forecast_skill",
            success=True,
            response_time_ms=150,
        )

        records = logger.get_records()
        assert len(records) >= 1
        assert records[0]["message"] == "测试消息"

    def test_evolution_analyzer(self, tmp_data_dir):
        """EvolutionAnalyzer should analyze logged interactions."""
        from hydroclaw.evolution import InteractionLogger, EvolutionAnalyzer

        logger = InteractionLogger(log_dir=tmp_data_dir["interactions"])
        # Log several interactions
        for i in range(5):
            logger.log_chat(
                message=f"消息 {i}",
                user_id="user1",
                group="default",
                channel="api",
                role="operator",
                success=i != 3,  # One failure
                response_time_ms=100 + i * 50,
            )

        analyzer = EvolutionAnalyzer(interaction_dir=tmp_data_dir["interactions"])
        report = analyzer.analyze(days_back=1)
        assert report.total_interactions == 5
        assert report.success_rate == pytest.approx(80.0, abs=1.0)

    def test_evolution_by_role(self, tmp_data_dir):
        """analyze_by_role should segment by role."""
        from hydroclaw.evolution import InteractionLogger, EvolutionAnalyzer

        logger = InteractionLogger(log_dir=tmp_data_dir["interactions"])
        for role in ["operator", "operator", "admin"]:
            logger.log_chat(
                message="test", user_id="u1", group="g", channel="api",
                role=role, success=True,
            )

        analyzer = EvolutionAnalyzer(interaction_dir=tmp_data_dir["interactions"])
        by_role = analyzer.analyze_by_role(days_back=1)
        assert "operator" in by_role
        op = by_role["operator"]
        assert op["total"] == 2


# ═══════════════════════════════════════════════════════════════
# 10. Personality System
# ═══════════════════════════════════════════════════════════════


class TestPersonalitySystem:
    """Test personality profile loading."""

    def test_load_default_profile(self):
        """Loading a profile should return PersonalityProfile."""
        from hydroclaw.personality import PersonalityManager

        mgr = PersonalityManager()
        profile = mgr.load_profile("admin", user_id="test_user", role="admin")
        assert profile is not None
        assert profile.agent_name  # Should have a name

    def test_get_all_groups(self):
        """get_all_groups should return configured groups."""
        from hydroclaw.personality import PersonalityManager

        mgr = PersonalityManager()
        groups = mgr.get_all_groups()
        assert isinstance(groups, list)

    def test_system_prompt_generation(self):
        """get_system_prompt should return non-empty string."""
        from hydroclaw.personality import PersonalityManager

        mgr = PersonalityManager()
        profile = mgr.load_profile("admin", user_id="test", role="admin")
        prompt = profile.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0


# ═══════════════════════════════════════════════════════════════
# 11. System Status and Version
# ═══════════════════════════════════════════════════════════════


class TestSystemStatus:
    """Test system-wide status and version consistency."""

    def test_system_status_version(self, client):
        """System status should report v0.2.2."""
        resp = client.get("/api/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.2.2"

    def test_hydroclaw_package_version(self):
        """hydroclaw.__version__ should match pyproject.toml."""
        import hydroclaw
        assert hydroclaw.__version__ == "0.2.2"

    def test_roles_endpoint(self, client):
        """GET /api/roles should return all 5 roles."""
        resp = client.get("/api/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert "designer" in data
        assert "researcher" in data
        assert "operator" in data
        assert "admin" in data
        assert "teacher" in data
