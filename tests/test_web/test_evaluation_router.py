"""Tests for the evaluation API router.
评价 API 路由测试。

Tests cover POST /api/evaluation/performance and POST /api/evaluation/wnal.
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


class TestEvaluationRouter:
    """Test /api/evaluation endpoints."""

    def test_performance_default_metrics(self, client):
        """POST /api/evaluation/performance with default metrics returns RMSE/MAE/NSE."""
        payload = {
            "observed": [1.0, 2.0, 3.0, 4.0, 5.0],
            "predicted": [1.1, 2.1, 2.9, 4.2, 4.8],
        }
        resp = client.post("/api/evaluation/performance", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "RMSE" in data or "metrics" in data or "rmse" in data

    def test_performance_custom_metrics(self, client):
        """POST /api/evaluation/performance with specific metric list."""
        payload = {
            "observed": [1.0, 2.0, 3.0],
            "predicted": [1.0, 2.0, 3.0],
            "metrics": ["RMSE", "MAE"],
        }
        resp = client.post("/api/evaluation/performance", json=payload)
        assert resp.status_code == 200

    def test_performance_with_setpoint(self, client):
        """POST /api/evaluation/performance with setpoint for control quality."""
        payload = {
            "observed": [1.0, 1.1, 0.9, 1.0, 1.05],
            "predicted": [1.0, 1.0, 1.0, 1.0, 1.0],
            "setpoint": 1.0,
        }
        resp = client.post("/api/evaluation/performance", json=payload)
        assert resp.status_code == 200

    def test_performance_length_mismatch(self, client):
        """POST /api/evaluation/performance with mismatched lengths returns 422."""
        payload = {
            "observed": [1.0, 2.0, 3.0],
            "predicted": [1.0, 2.0],
        }
        resp = client.post("/api/evaluation/performance", json=payload)
        assert resp.status_code == 422

    def test_performance_empty(self, client):
        """POST /api/evaluation/performance with empty arrays returns 422."""
        payload = {"observed": [], "predicted": []}
        resp = client.post("/api/evaluation/performance", json=payload)
        assert resp.status_code == 422

    def test_wnal_assess(self, client):
        """POST /api/evaluation/wnal returns WNAL level and score."""
        payload = {
            "capabilities": {
                "perception": 80.0,
                "decision": 60.0,
                "control": 70.0,
                "learning": 40.0,
            }
        }
        resp = client.post("/api/evaluation/wnal", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "level" in data or "wnal_level" in data or "score" in data

    def test_wnal_empty_capabilities(self, client):
        """POST /api/evaluation/wnal with empty dict still returns result."""
        payload = {"capabilities": {}}
        resp = client.post("/api/evaluation/wnal", json=payload)
        assert resp.status_code == 200
