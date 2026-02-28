"""Tests for the identification API router.
系统辨识 API 路由测试。

Tests cover POST /api/identification/run and POST /api/identification/arx.
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


class TestIdentificationRouter:
    """Test /api/identification endpoints."""

    def test_run_nonlinear(self, client):
        """POST /api/identification/run with nonlinear model returns params."""
        payload = {
            "observed_h": [0.5, 0.48, 0.46, 0.44, 0.42],
            "observed_q_out": [0.01, 0.0098, 0.0096, 0.0094, 0.0092],
            "model_type": "nonlinear",
        }
        resp = client.post("/api/identification/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_run_arx_model(self, client):
        """POST /api/identification/run with ARX model type."""
        payload = {
            "observed_h": [0.5, 0.48, 0.46, 0.44, 0.42],
            "observed_q_out": [0.01, 0.0098, 0.0096, 0.0094, 0.0092],
            "model_type": "ARX",
        }
        resp = client.post("/api/identification/run", json=payload)
        assert resp.status_code == 200

    def test_run_with_initial_guess(self, client):
        """POST /api/identification/run with initial guess."""
        payload = {
            "observed_h": [0.5, 0.48, 0.46, 0.44, 0.42],
            "observed_q_out": [0.01, 0.0098, 0.0096, 0.0094, 0.0092],
            "model_type": "nonlinear",
            "initial_guess": {"cd": 0.6, "area_ratio": 0.01},
        }
        resp = client.post("/api/identification/run", json=payload)
        assert resp.status_code == 200

    def test_run_length_mismatch(self, client):
        """POST /api/identification/run with mismatched lengths returns 422."""
        payload = {
            "observed_h": [0.5, 0.48, 0.46],
            "observed_q_out": [0.01, 0.0098],
        }
        resp = client.post("/api/identification/run", json=payload)
        assert resp.status_code == 422

    def test_run_too_short(self, client):
        """POST /api/identification/run with < 3 data points returns 422."""
        payload = {
            "observed_h": [0.5, 0.48],
            "observed_q_out": [0.01, 0.0098],
        }
        resp = client.post("/api/identification/run", json=payload)
        assert resp.status_code == 422

    def test_arx_endpoint(self, client):
        """POST /api/identification/arx with valid data returns ARX params."""
        payload = {
            "y": [1.0, 0.95, 0.91, 0.87, 0.83, 0.80],
            "u": [0.01, 0.0095, 0.0091, 0.0087, 0.0083, 0.0080],
            "na": 2,
            "nb": 2,
        }
        resp = client.post("/api/identification/arx", json=payload)
        assert resp.status_code == 200

    def test_arx_length_mismatch(self, client):
        """POST /api/identification/arx with mismatched y/u returns 422."""
        payload = {
            "y": [1.0, 0.95, 0.91, 0.87],
            "u": [0.01, 0.0095, 0.0091],
            "na": 2,
            "nb": 2,
        }
        resp = client.post("/api/identification/arx", json=payload)
        assert resp.status_code == 422
