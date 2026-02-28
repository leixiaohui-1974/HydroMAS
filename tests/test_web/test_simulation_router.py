"""Tests for the simulation API router.
仿真 API 路由测试。

Tests cover POST /api/simulation/run (various configs) and GET /api/simulation/defaults.
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


class TestSimulationRouter:
    """Test /api/simulation endpoints."""

    def test_run_default(self, client):
        """POST /api/simulation/run with defaults returns result with times/h."""
        payload = {}
        resp = client.post("/api/simulation/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "time" in data or "water_level" in data

    def test_run_custom_duration(self, client):
        """POST /api/simulation/run with custom duration."""
        payload = {"duration": 60, "dt": 1.0, "initial_h": 0.3}
        resp = client.post("/api/simulation/run", json=payload)
        assert resp.status_code == 200

    def test_run_euler_solver(self, client):
        """POST /api/simulation/run with euler solver."""
        payload = {"duration": 30, "dt": 1.0, "solver": "euler"}
        resp = client.post("/api/simulation/run", json=payload)
        assert resp.status_code == 200

    def test_run_rk4_solver(self, client):
        """POST /api/simulation/run with rk4 solver."""
        payload = {"duration": 30, "dt": 1.0, "solver": "rk4"}
        resp = client.post("/api/simulation/run", json=payload)
        assert resp.status_code == 200

    def test_run_custom_inflow_profile(self, client):
        """POST /api/simulation/run with custom q_in_profile."""
        payload = {
            "duration": 60,
            "dt": 1.0,
            "initial_h": 0.5,
            "q_in_profile": [[0, 0.01], [30, 0.02]],
        }
        resp = client.post("/api/simulation/run", json=payload)
        assert resp.status_code == 200

    def test_run_invalid_duration(self, client):
        """POST /api/simulation/run with negative duration returns 422."""
        payload = {"duration": -10}
        resp = client.post("/api/simulation/run", json=payload)
        assert resp.status_code == 422

    def test_run_too_many_steps(self, client):
        """POST /api/simulation/run with excessive steps returns 422."""
        payload = {"duration": 86400, "dt": 0.001}
        resp = client.post("/api/simulation/run", json=payload)
        assert resp.status_code == 422

    def test_defaults(self, client):
        """GET /api/simulation/defaults returns tank_params and simulation_params."""
        resp = client.get("/api/simulation/defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert "tank_params" in data
        assert "simulation_params" in data
