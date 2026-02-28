"""Tests for the scheduling API router.
调度 API 路由测试。

Tests cover POST /api/scheduling/run with LP and rule-based methods.
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


class TestSchedulingRouter:
    """Test /api/scheduling endpoints."""

    def test_run_lp(self, client):
        """POST /api/scheduling/run with LP method returns schedule."""
        payload = {
            "demand_forecast": [0.01, 0.02, 0.015, 0.03, 0.025],
            "supply_capacity": 0.05,
            "method": "lp",
            "objective": "minimize_cost",
        }
        resp = client.post("/api/scheduling/run", json=payload)
        assert resp.status_code == 200

    def test_run_rule(self, client):
        """POST /api/scheduling/run with rule-based method."""
        payload = {
            "demand_forecast": [0.01, 0.02, 0.015],
            "supply_capacity": 0.05,
            "method": "rule",
        }
        resp = client.post("/api/scheduling/run", json=payload)
        assert resp.status_code == 200

    def test_run_maximize_supply(self, client):
        """POST /api/scheduling/run with maximize_supply objective."""
        payload = {
            "demand_forecast": [0.01, 0.02, 0.015],
            "supply_capacity": 0.05,
            "objective": "maximize_supply",
        }
        resp = client.post("/api/scheduling/run", json=payload)
        assert resp.status_code == 200

    def test_run_with_constraints(self, client):
        """POST /api/scheduling/run with extra constraints."""
        payload = {
            "demand_forecast": [0.01, 0.02],
            "supply_capacity": 0.05,
            "constraints": {"min_level": 0.3, "max_level": 2.0},
        }
        resp = client.post("/api/scheduling/run", json=payload)
        assert resp.status_code == 200

    def test_run_missing_demand(self, client):
        """POST /api/scheduling/run with no demand returns 422."""
        payload = {"supply_capacity": 0.05}
        resp = client.post("/api/scheduling/run", json=payload)
        assert resp.status_code == 422

    def test_run_empty_demand(self, client):
        """POST /api/scheduling/run with empty demand returns 422."""
        payload = {"demand_forecast": []}
        resp = client.post("/api/scheduling/run", json=payload)
        assert resp.status_code == 422
