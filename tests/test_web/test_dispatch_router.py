"""Phase 3 tests for the dispatch API router.
Phase 3 调度优化 API 路由测试。

Tests cover POST /api/dispatch/optimize, invalid request handling,
and result structure validation.
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


class TestDispatchRouter:
    """Test /api/dispatch endpoints."""

    def test_optimize_dispatch_endpoint(self, client):
        """POST /api/dispatch/optimize with valid data returns allocation."""
        payload = {
            "demand_forecast": {
                "workshop_A": 200,
                "workshop_B": 150,
                "workshop_C": 100,
            },
            "supply_config": {
                "river": {"capacity": 300},
                "well": {"capacity": 200},
            },
            "reuse_config": {"available_volume": 50},
            "method": "lp",
        }
        resp = client.post("/api/dispatch/optimize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_demand" in data
        assert "total_supply" in data
        assert "allocation" in data
        assert "feasible" in data
        assert data["total_demand"] == 450
        assert data["total_supply"] == 500

    def test_optimize_dispatch_invalid(self, client):
        """POST /api/dispatch/optimize with missing supply_config returns 422."""
        payload = {
            "demand_forecast": {"workshop_A": 200},
            # supply_config is missing
        }
        resp = client.post("/api/dispatch/optimize", json=payload)
        assert resp.status_code == 422

    def test_optimize_dispatch_feasibility(self, client):
        """When supply exceeds demand, result should be feasible."""
        payload = {
            "demand_forecast": {"ws1": 100},
            "supply_config": {"source1": {"capacity": 200}},
            "method": "lp",
        }
        resp = client.post("/api/dispatch/optimize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["feasible"] is True
        assert data["deficit"] == 0

    def test_optimize_dispatch_result_has_method(self, client):
        """Result should echo back the method used."""
        payload = {
            "demand_forecast": {"ws1": 50},
            "supply_config": {"src1": {"capacity": 100}},
            "method": "lp",
        }
        resp = client.post("/api/dispatch/optimize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "method" in data
        assert data["method"] == "lp"
