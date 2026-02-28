"""Tests for Phase 5 observability API endpoints.
Phase 5 可观测性 API 端点测试。

Tests cover:
- GET /api/orchestration/traces (list traces)
- GET /api/orchestration/traces/{trace_id} (trace detail)
- GET /api/orchestration/spans (query spans)
- GET /api/orchestration/circuit-breakers (list breakers)
- POST /api/orchestration/circuit-breakers/{id}/reset
- GET /api/orchestration/rate-limits
- POST /api/orchestration/rate-limits/{agent_id}
- GET /api/orchestration/health/deep
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


class TestTracingEndpoints:
    def test_list_traces(self, client):
        resp = client.get("/api/orchestration/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_traces" in data
        assert "total_spans" in data
        assert "traces" in data

    def test_get_nonexistent_trace(self, client):
        resp = client.get("/api/orchestration/traces/nonexistent-trace-id")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_query_spans(self, client):
        resp = client.get("/api/orchestration/spans")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "spans" in data

    def test_query_spans_with_invalid_status(self, client):
        resp = client.get("/api/orchestration/spans?status=invalid")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


class TestCircuitBreakerEndpoints:
    def test_list_circuit_breakers(self, client):
        resp = client.get("/api/orchestration/circuit-breakers")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "open_count" in data
        assert "breakers" in data

    def test_reset_circuit_breaker(self, client):
        resp = client.post("/api/orchestration/circuit-breakers/planning/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "planning"
        assert data["status"] == "closed"


class TestRateLimitEndpoints:
    def test_list_rate_limits(self, client):
        resp = client.get("/api/orchestration/rate-limits")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "limiters" in data

    def test_configure_rate_limit(self, client):
        resp = client.post(
            "/api/orchestration/rate-limits/planning?rate=5.0&capacity=10.0"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "planning"
        assert data["configured"]["rate"] == 5.0
        assert data["configured"]["capacity"] == 10.0


class TestDeepHealthEndpoint:
    def test_deep_health_check(self, client):
        resp = client.get("/api/orchestration/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert "platform" in data
        assert "circuit_breakers" in data
        assert "rate_limiters" in data
        assert "tracing" in data

    def test_deep_health_has_agent_count(self, client):
        resp = client.get("/api/orchestration/health/deep")
        data = resp.json()
        assert data["agents"]["total"] == 15
