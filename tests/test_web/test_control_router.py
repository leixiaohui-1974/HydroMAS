"""Tests for the control API router.
控制 API 路由测试。

Tests cover POST /api/control/run (PID/MPC) and GET /api/control/defaults.
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


class TestControlRouter:
    """Test /api/control endpoints."""

    def test_run_pid_default(self, client):
        """POST /api/control/run with PID defaults returns result."""
        payload = {"setpoint": 1.0, "controller_type": "PID"}
        resp = client.post("/api/control/run", json=payload)
        assert resp.status_code == 200

    def test_run_mpc_default(self, client):
        """POST /api/control/run with MPC defaults returns result."""
        payload = {"setpoint": 1.0, "controller_type": "MPC"}
        resp = client.post("/api/control/run", json=payload)
        assert resp.status_code == 200

    def test_run_custom_setpoint(self, client):
        """POST /api/control/run with custom setpoint."""
        payload = {
            "setpoint": 2.0,
            "controller_type": "PID",
            "duration": 60,
            "dt": 1.0,
            "initial_h": 0.5,
        }
        resp = client.post("/api/control/run", json=payload)
        assert resp.status_code == 200

    def test_run_invalid_controller_type(self, client):
        """POST /api/control/run with invalid type returns 422."""
        payload = {"setpoint": 1.0, "controller_type": "INVALID"}
        resp = client.post("/api/control/run", json=payload)
        assert resp.status_code == 422

    def test_run_negative_setpoint(self, client):
        """POST /api/control/run with negative setpoint returns 422."""
        payload = {"setpoint": -1.0}
        resp = client.post("/api/control/run", json=payload)
        assert resp.status_code == 422

    def test_run_too_many_steps(self, client):
        """POST /api/control/run with excessive steps returns 422."""
        payload = {"setpoint": 1.0, "duration": 86400, "dt": 0.001}
        resp = client.post("/api/control/run", json=payload)
        assert resp.status_code == 422

    def test_defaults(self, client):
        """GET /api/control/defaults returns pid and mpc params."""
        resp = client.get("/api/control/defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert "pid" in data
        assert "mpc" in data
