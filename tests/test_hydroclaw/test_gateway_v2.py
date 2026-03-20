"""Tests for HydroClaw enhanced Gateway v2.
HydroClaw 增强网关 v2 测试。
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from web.app import app
    return TestClient(app)


class TestGatewayRoles:
    """Test enhanced roles endpoint (5 roles)."""

    def test_get_roles(self, client):
        resp = client.get("/api/gateway/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert "roles" in data
        roles = data["roles"]
        assert "operator" in roles
        assert "designer" in roles
        assert "researcher" in roles
        assert "admin" in roles
        assert "teacher" in roles

    def test_role_has_permissions(self, client):
        resp = client.get("/api/gateway/roles")
        data = resp.json()
        operator = data["roles"]["operator"]
        assert "permissions" in operator
        assert "name" in operator
        assert "name_en" in operator

    def test_role_actions(self, client):
        resp = client.get("/api/gateway/roles/operator/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "operator"
        assert len(data["actions"]) > 0

    def test_teacher_role_actions(self, client):
        resp = client.get("/api/gateway/roles/teacher/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "teacher"

    def test_admin_role_actions(self, client):
        resp = client.get("/api/gateway/roles/admin/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert any("心跳" in a["label"] or "自进化" in a["label"] for a in data["actions"])

    def test_unknown_role_actions(self, client):
        resp = client.get("/api/gateway/roles/unknown/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


class TestGatewayCognitive:
    """Test cognitive API categories."""

    def test_get_categories(self, client):
        resp = client.get("/api/gateway/cognitive")
        assert resp.status_code == 200
        data = resp.json()
        cats = data["categories"]
        assert "perception" in cats
        assert "cognition" in cats
        assert "decision" in cats
        assert "control" in cats

    def test_category_detail(self, client):
        resp = client.get("/api/gateway/cognitive/perception")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "perception"
        assert "skills" in data
        assert "apis" in data

    def test_unknown_category(self, client):
        resp = client.get("/api/gateway/cognitive/unknown")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


class TestGatewayChat:
    """Test enhanced chat endpoint."""

    def test_chat_basic(self, client):
        resp = client.post("/api/gateway/chat", json={
            "message": "你好",
            "role": "operator",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "intent" in data
        assert "role" in data
        assert data["role"] == "operator"

    def test_chat_with_user_id(self, client):
        resp = client.post("/api/gateway/chat", json={
            "message": "水平衡查询",
            "role": "operator",
            "user_id": "test_user",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "test_user"

    def test_chat_admin_role(self, client):
        resp = client.post("/api/gateway/chat", json={
            "message": "系统状态",
            "role": "admin",
        })
        assert resp.status_code == 200

    def test_chat_teacher_role(self, client):
        resp = client.post("/api/gateway/chat", json={
            "message": "仿真演示",
            "role": "teacher",
        })
        assert resp.status_code == 200

    def test_chat_has_session_id(self, client):
        resp = client.post("/api/gateway/chat", json={
            "message": "测试会话",
            "role": "operator",
            "user_id": "session_test_user",
        })
        data = resp.json()
        assert "session_id" in data


class TestGatewaySkills:
    """Test skills endpoint with RBAC."""

    def test_list_skills(self, client):
        resp = client.get("/api/gateway/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert data["total"] > 0

    def test_list_skills_filtered_by_role(self, client):
        resp = client.get("/api/gateway/skills?role=operator")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role_filter"] == "operator"

    def test_skills_have_permission_field(self, client):
        resp = client.get("/api/gateway/skills?role=researcher")
        data = resp.json()
        if data["skills"]:
            assert "permission" in data["skills"][0]


class TestGatewayHealth:
    """Test health endpoint with heartbeat."""

    def test_health(self, client):
        resp = client.get("/api/gateway/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "platform" in data
        assert data["platform"]["name"] == "HydroMAS"
        assert "heartbeat" in data


class TestGatewaySessions:
    """Test session management endpoint."""

    def test_list_sessions(self, client):
        resp = client.get("/api/gateway/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "total" in data
        assert "scope" in data


class TestGatewayHeartbeat:
    """Test heartbeat endpoints."""

    def test_heartbeat_status(self, client):
        resp = client.get("/api/gateway/heartbeat/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "checks" in data

    def test_heartbeat_run(self, client):
        resp = client.post("/api/gateway/heartbeat/run?check_name=resource_monitor")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 1


class TestGatewayEvolution:
    """Test evolution/self-improvement endpoints."""

    def test_evolution_stats(self, client):
        resp = client.get("/api/gateway/evolution/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data

    def test_evolution_report(self, client):
        resp = client.get("/api/gateway/evolution/report?days=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "analysis_date" in data
        assert "improvements" in data


class TestGatewayMemory:
    """Test memory endpoints."""

    def test_get_memory(self, client):
        resp = client.get("/api/gateway/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert "group" in data
        assert "memory" in data

    def test_memory_search(self, client):
        resp = client.get("/api/gateway/memory/search?query=水平衡")
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "results" in data


class TestGatewayPersonality:
    """Test personality endpoint."""

    def test_get_personality(self, client):
        resp = client.get("/api/gateway/personality")
        assert resp.status_code == 200
        data = resp.json()
        assert "group" in data
        assert "role" in data
        assert "agent_name" in data
        assert "agent_emoji" in data


class TestGatewayDashboard:
    """Test enhanced dashboard endpoint."""

    def test_dashboard(self, client):
        resp = client.get("/api/gateway/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "HydroMAS"
        assert "agents" in data
        assert "skills" in data
        assert "roles" in data
        assert "cognitive_categories" in data
        assert "sessions" in data
        assert "heartbeat" in data
        assert "teacher" in data["roles"]
