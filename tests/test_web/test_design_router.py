"""Tests for the design API router.
设计 API 路由测试。

Tests cover POST /api/design/sensitivity and POST /api/design/sizing.
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


class TestDesignRouter:
    """Test /api/design endpoints."""

    def test_sensitivity_oat(self, client):
        """POST /api/design/sensitivity with OAT method returns results."""
        payload = {
            "base_params": {"area": 1.0, "cd": 0.6},
            "param_ranges": {
                "area": [0.5, 2.0],
                "cd": [0.3, 0.9],
            },
            "method": "OAT",
            "n_levels": 5,
        }
        resp = client.post("/api/design/sensitivity", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_sensitivity_morris(self, client):
        """POST /api/design/sensitivity with Morris method."""
        payload = {
            "base_params": {"area": 1.0, "cd": 0.6},
            "param_ranges": {
                "area": [0.5, 2.0],
                "cd": [0.3, 0.9],
            },
            "method": "Morris",
            "n_levels": 5,
        }
        resp = client.post("/api/design/sensitivity", json=payload)
        assert resp.status_code == 200

    def test_sensitivity_too_many_evaluations(self, client):
        """POST /api/design/sensitivity with excessive evaluations returns 422."""
        payload = {
            "base_params": {"a": 1.0},
            "param_ranges": {"a": [0, 10], "b": [0, 10], "c": [0, 10]},
            "n_levels": 1000,  # 1000 * 3 = 3000 < 5000, ok. Need > 5000
        }
        # With 6 params × 1000 levels = 6000 > 5000 limit
        payload["param_ranges"] = {
            f"p{i}": [0, 10] for i in range(6)
        }
        payload["base_params"] = {f"p{i}": 5.0 for i in range(6)}
        resp = client.post("/api/design/sensitivity", json=payload)
        assert resp.status_code == 422

    def test_sensitivity_missing_params(self, client):
        """POST /api/design/sensitivity with missing base_params returns 422."""
        payload = {"param_ranges": {"a": [0, 10]}}
        resp = client.post("/api/design/sensitivity", json=payload)
        assert resp.status_code == 422

    def test_sizing_default(self, client):
        """POST /api/design/sizing with defaults returns tank size."""
        payload = {}
        resp = client.post("/api/design/sizing", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_sizing_custom(self, client):
        """POST /api/design/sizing with custom parameters."""
        payload = {
            "demand_peak": 0.05,
            "duration_hours": 8.0,
            "safety_factor": 1.5,
        }
        resp = client.post("/api/design/sizing", json=payload)
        assert resp.status_code == 200

    def test_sizing_invalid_safety_factor(self, client):
        """POST /api/design/sizing with safety_factor < 1.0 returns 422."""
        payload = {"safety_factor": 0.5}
        resp = client.post("/api/design/sizing", json=payload)
        assert resp.status_code == 422
