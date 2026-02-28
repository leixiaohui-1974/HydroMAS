"""Tests for Phase 6 intelligence API endpoints.
Phase 6 智能升级 API 端点测试。

Tests cover:
- POST /api/orchestration/intent (classify intent)
- GET  /api/orchestration/intent/history
- GET  /api/orchestration/scheduling/status
- GET  /api/orchestration/scheduling/profiles
- GET  /api/orchestration/scheduling/recommend/{agent_id}/{action}
- GET  /api/orchestration/negotiation/history
"""

import pytest

try:
    from fastapi.testclient import TestClient

    from web.app import app
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="FastAPI not installed")


@pytest.fixture
def client():
    return TestClient(app)


class TestIntentEndpoints:
    def test_classify_simple_intent(self, client):
        resp = client.post(
            "/api/orchestration/intent",
            json={"user_input": "请进行水位预报分析"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "route_type" in data
        assert "target" in data
        assert "confidence" in data
        assert "domain" in data

    def test_classify_compound_intent(self, client):
        resp = client.post(
            "/api/orchestration/intent",
            json={
                "user_input": "先预测水位然后检查ODD安全",
                "compound": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compound"] is True
        assert "intents" in data
        assert "count" in data

    def test_classify_fallback(self, client):
        resp = client.post(
            "/api/orchestration/intent",
            json={"user_input": "你好"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["route_type"] == "planning"

    def test_intent_history(self, client):
        # Classify something first to ensure history has entries
        client.post(
            "/api/orchestration/intent",
            json={"user_input": "预测水位"},
        )
        resp = client.get("/api/orchestration/intent/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert "stats" in data


class TestSchedulingEndpoints:
    def test_scheduling_status(self, client):
        resp = client.get("/api/orchestration/scheduling/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_agents_profiled" in data
        assert "total_actions_tracked" in data

    def test_scheduling_profiles(self, client):
        resp = client.get("/api/orchestration/scheduling/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert "profiles" in data

    def test_scheduling_recommend(self, client):
        resp = client.get("/api/orchestration/scheduling/recommend/planning/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "planning"
        assert data["action"] == "analyze"
        assert "recommended_timeout_sec" in data
        assert "recommended_max_retries" in data


class TestNegotiationHistoryEndpoint:
    def test_negotiation_history(self, client):
        resp = client.get("/api/orchestration/negotiation/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert "preferences" in data
