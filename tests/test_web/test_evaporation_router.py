"""Phase 3 tests for the evaporation API router.
Phase 3 蒸发预测 API 路由测试。

Tests cover POST /api/evaporation/predict, invalid request handling,
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


def _sample_tower_params():
    """Return valid cooling tower parameters."""
    return {
        "water_flow_m3h": 500.0,
        "t_in": 42.0,
        "t_out": 32.0,
        "n_cells": 4,
        "fan_power_kw": 55.0,
    }


def _sample_weather():
    """Return valid weather conditions."""
    return {
        "t_db": 35.0,
        "t_wb": 28.0,
        "humidity": 0.6,
        "wind_speed": 3.0,
    }


class TestEvaporationRouter:
    """Test /api/evaporation endpoints."""

    def test_predict_evaporation_endpoint(self, client):
        """POST /api/evaporation/predict with valid data returns prediction."""
        payload = {
            "tower_params": _sample_tower_params(),
            "weather": _sample_weather(),
        }
        resp = client.post("/api/evaporation/predict", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "evap_rate_m3h" in data
        assert "evap_daily_m3" in data
        assert data["evap_rate_m3h"] > 0
        assert data["evap_daily_m3"] > 0

    def test_predict_evaporation_invalid(self, client):
        """POST /api/evaporation/predict with missing weather returns 422."""
        payload = {
            "tower_params": _sample_tower_params(),
            # weather is missing
        }
        resp = client.post("/api/evaporation/predict", json=payload)
        assert resp.status_code == 422

    def test_predict_evaporation_zero_flow(self, client):
        """POST /api/evaporation/predict with zero flow returns 400 error."""
        payload = {
            "tower_params": {
                "water_flow_m3h": 0,  # Invalid: must be positive
                "t_in": 42.0,
                "t_out": 32.0,
            },
            "weather": _sample_weather(),
        }
        resp = client.post("/api/evaporation/predict", json=payload)
        # The evaporation_server raises ValueError for non-positive flow
        assert resp.status_code == 400

    def test_predict_evaporation_result_keys(self, client):
        """Result should contain evap_ratio key."""
        payload = {
            "tower_params": _sample_tower_params(),
            "weather": _sample_weather(),
        }
        resp = client.post("/api/evaporation/predict", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "evap_ratio" in data
        assert isinstance(data["evap_ratio"], (int, float))
