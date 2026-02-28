"""Tests for Gateway API endpoints — OpenClaw integration layer.
网关 API 端点测试 — OpenClaw 集成层。

Tests the /api/gateway/* endpoints that OpenClaw uses to call HydroMAS.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web.app import app

client = TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Gateway chat endpoint
# ===========================================================================

class TestGatewayChat:
    def test_chat_basic(self):
        resp = client.post(
            "/api/gateway/chat",
            json={"message": "你好", "role": "operator"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "intent" in data
        assert data["role"] == "operator"
        assert "elapsed_ms" in data

    def test_chat_researcher_role(self):
        resp = client.post(
            "/api/gateway/chat",
            json={"message": "运行水箱仿真模拟", "role": "researcher"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "researcher"

    def test_chat_designer_role(self):
        resp = client.post(
            "/api/gateway/chat",
            json={"message": "设计PID控制器", "role": "designer"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "designer"

    def test_chat_with_session_id(self):
        resp = client.post(
            "/api/gateway/chat",
            json={
                "message": "查看水平衡",
                "role": "operator",
                "session_id": "sess_001",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "sess_001"

    def test_chat_with_params(self):
        resp = client.post(
            "/api/gateway/chat",
            json={
                "message": "分析数据",
                "role": "researcher",
                "params": {"horizon": 24},
            },
        )
        assert resp.status_code == 200

    def test_chat_intent_classification(self):
        resp = client.post(
            "/api/gateway/chat",
            json={"message": "预报未来水位变化", "role": "operator"},
        )
        data = resp.json()
        assert "intent" in data
        assert "route_type" in data["intent"]
        assert "domain" in data["intent"]

    def test_chat_empty_message_rejected(self):
        resp = client.post(
            "/api/gateway/chat",
            json={"message": "", "role": "operator"},
        )
        assert resp.status_code == 422


# ===========================================================================
# Gateway skill endpoint
# ===========================================================================

class TestGatewaySkill:
    def test_skill_unknown(self):
        resp = client.post(
            "/api/gateway/skill",
            json={"skill_name": "nonexistent_skill"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "not found" in data["error"]
        assert "available_skills" in data

    def test_skill_name_required(self):
        resp = client.post(
            "/api/gateway/skill",
            json={"params": {}},
        )
        assert resp.status_code == 422


# ===========================================================================
# Gateway roles endpoint
# ===========================================================================

class TestGatewayRoles:
    def test_get_roles(self):
        resp = client.get("/api/gateway/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert "roles" in data
        assert "researcher" in data["roles"]
        assert "designer" in data["roles"]
        assert "operator" in data["roles"]

    def test_role_profiles_have_required_fields(self):
        resp = client.get("/api/gateway/roles")
        for role_name, profile in resp.json()["roles"].items():
            assert "name" in profile
            assert "name_en" in profile
            assert "description" in profile
            assert "capabilities" in profile
            assert "quick_actions" in profile

    def test_get_role_actions_operator(self):
        resp = client.get("/api/gateway/roles/operator/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "operator"
        assert len(data["actions"]) > 0
        for action in data["actions"]:
            assert "label" in action
            assert "message" in action

    def test_get_role_actions_researcher(self):
        resp = client.get("/api/gateway/roles/researcher/actions")
        assert resp.status_code == 200
        assert len(resp.json()["actions"]) > 0

    def test_get_role_actions_designer(self):
        resp = client.get("/api/gateway/roles/designer/actions")
        assert resp.status_code == 200
        assert len(resp.json()["actions"]) > 0

    def test_get_role_actions_unknown(self):
        resp = client.get("/api/gateway/roles/unknown_role/actions")
        assert resp.status_code == 200
        assert "error" in resp.json()


# ===========================================================================
# Gateway skills listing
# ===========================================================================

class TestGatewaySkills:
    def test_list_all_skills(self):
        resp = client.get("/api/gateway/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert "total" in data
        assert data["total"] > 0

    def test_list_skills_filtered_by_role(self):
        resp_all = client.get("/api/gateway/skills")
        resp_op = client.get("/api/gateway/skills?role=operator")
        assert resp_op.status_code == 200
        data = resp_op.json()
        assert data["role_filter"] == "operator"

    def test_skill_entry_format(self):
        resp = client.get("/api/gateway/skills")
        skills = resp.json()["skills"]
        if skills:
            s = skills[0]
            assert "name" in s
            assert "has_instance" in s


# ===========================================================================
# Gateway health endpoint
# ===========================================================================

class TestGatewayHealth:
    def test_health(self):
        resp = client.get("/api/gateway/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "agents_registered" in data
        assert data["agents_registered"] > 0
        assert "platform" in data


# ===========================================================================
# HydroMAS Client SDK tests
# ===========================================================================

class TestHydroMASClient:
    def test_client_import(self):
        from openclaw.hydromas_client import HydroMASClient, HydroMASResponse
        client = HydroMASClient("http://localhost:8000")
        assert client.base_url == "http://localhost:8000"

    def test_client_response_to_markdown(self):
        from openclaw.hydromas_client import HydroMASResponse
        resp = HydroMASResponse(
            success=True,
            data={"status": "ok", "value": 42},
        )
        md = resp.to_markdown()
        assert "status" in md
        assert "42" in md

    def test_client_error_response(self):
        from openclaw.hydromas_client import HydroMASResponse
        resp = HydroMASResponse(
            success=False,
            error="Connection refused",
        )
        md = resp.to_markdown()
        assert "Error" in md

    def test_client_trailing_slash_stripped(self):
        from openclaw.hydromas_client import HydroMASClient
        client = HydroMASClient("http://example.com/")
        assert client.base_url == "http://example.com"

    def test_client_connection_error(self):
        from openclaw.hydromas_client import HydroMASClient
        client = HydroMASClient("http://localhost:19999", timeout=2)
        resp = client.health_check()
        assert resp.success is False
        assert "connection" in resp.status.lower() or "error" in resp.status.lower()
