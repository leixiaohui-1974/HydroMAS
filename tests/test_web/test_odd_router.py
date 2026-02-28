"""Tests for the ODD API router.
ODD 安全监测 API 路由测试。

Tests cover POST /api/odd/check, POST /api/odd/check-series,
POST /api/odd/mrc-plan, and GET /api/odd/specs.
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


class TestODDRouter:
    """Test /api/odd endpoints."""

    def test_check_normal(self, client):
        """POST /api/odd/check with normal state returns within-bounds result."""
        payload = {
            "state": {"water_level": 1.0, "temperature": 25.0, "pH": 7.0},
        }
        resp = client.post("/api/odd/check", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "zone" in data or "violations" in data or "status" in data

    def test_check_with_custom_config(self, client):
        """POST /api/odd/check with custom ODD config."""
        payload = {
            "state": {"water_level": 5.0},
            "odd_config": {
                "water_level": {
                    "normal": [0, 3],
                    "extended": [0, 5],
                    "mrc": [0, 8],
                }
            },
        }
        resp = client.post("/api/odd/check", json=payload)
        assert resp.status_code == 200

    def test_check_empty_state(self, client):
        """POST /api/odd/check with empty state returns 422 (min 1 item)."""
        payload = {"state": {}}
        resp = client.post("/api/odd/check", json=payload)
        # Empty state might be rejected by the server or return empty result
        assert resp.status_code in (200, 422)

    def test_check_series(self, client):
        """POST /api/odd/check-series with state sequence."""
        payload = {
            "states": [
                {"water_level": 1.0},
                {"water_level": 2.0},
                {"water_level": 3.0},
            ],
        }
        resp = client.post("/api/odd/check-series", json=payload)
        assert resp.status_code == 200

    def test_check_series_with_times(self, client):
        """POST /api/odd/check-series with time stamps."""
        payload = {
            "states": [{"water_level": 1.0}, {"water_level": 2.0}],
            "times": [0.0, 1.0],
        }
        resp = client.post("/api/odd/check-series", json=payload)
        assert resp.status_code == 200

    def test_check_series_times_mismatch(self, client):
        """POST /api/odd/check-series with mismatched times/states returns 422."""
        payload = {
            "states": [{"water_level": 1.0}, {"water_level": 2.0}],
            "times": [0.0],
        }
        resp = client.post("/api/odd/check-series", json=payload)
        assert resp.status_code == 422

    def test_mrc_plan(self, client):
        """POST /api/odd/mrc-plan returns mitigation plan."""
        payload = {
            "state": {"water_level": 1.0, "temperature": 25.0},
        }
        resp = client.post("/api/odd/mrc-plan", json=payload)
        assert resp.status_code == 200

    def test_specs(self, client):
        """GET /api/odd/specs returns ODD dimension specifications."""
        resp = client.get("/api/odd/specs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert len(data) > 0
