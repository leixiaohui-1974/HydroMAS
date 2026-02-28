"""Tests for the prediction API router.
预测 API 路由测试。

Tests cover POST /api/prediction/run (linear/polynomial) and GET /api/prediction/sample-data.
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


class TestPredictionRouter:
    """Test /api/prediction endpoints."""

    def test_run_linear(self, client):
        """POST /api/prediction/run with linear model returns forecast."""
        payload = {
            "historical_data": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5],
            "horizon": 5,
            "model": "linear",
        }
        resp = client.post("/api/prediction/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "backtest_fitted" in data or "confidence_upper" in data

    def test_run_polynomial(self, client):
        """POST /api/prediction/run with polynomial model."""
        payload = {
            "historical_data": [1.0, 1.1, 1.3, 1.6, 2.0, 2.5],
            "horizon": 3,
            "model": "polynomial",
            "degree": 2,
        }
        resp = client.post("/api/prediction/run", json=payload)
        assert resp.status_code == 200

    def test_run_with_lookback(self, client):
        """POST /api/prediction/run with lookback window."""
        payload = {
            "historical_data": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6],
            "horizon": 3,
            "model": "linear",
            "lookback": 4,
        }
        resp = client.post("/api/prediction/run", json=payload)
        assert resp.status_code == 200

    def test_run_too_short_data(self, client):
        """POST /api/prediction/run with < 2 data points returns 422."""
        payload = {"historical_data": [1.0], "horizon": 5}
        resp = client.post("/api/prediction/run", json=payload)
        assert resp.status_code == 422

    def test_run_invalid_model(self, client):
        """POST /api/prediction/run with invalid model returns 422."""
        payload = {
            "historical_data": [1.0, 2.0, 3.0],
            "horizon": 3,
            "model": "neural_network",
        }
        resp = client.post("/api/prediction/run", json=payload)
        assert resp.status_code == 422

    def test_sample_data(self, client):
        """GET /api/prediction/sample-data returns sample time series."""
        resp = client.get("/api/prediction/sample-data")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert len(data) > 0
