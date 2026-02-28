"""Tests for the dataclean API router.
数据清洗 API 路由测试。

Tests cover POST /api/dataclean/outliers and POST /api/dataclean/interpolate.
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


class TestDataCleanRouter:
    """Test /api/dataclean endpoints."""

    def test_outliers_3sigma(self, client):
        """POST /api/dataclean/outliers with 3sigma method detects outliers."""
        payload = {
            "data": [1.0, 1.1, 1.0, 0.9, 1.0, 1.1, 10.0, 1.0, 0.9],
            "method": "3sigma",
            "threshold": 3.0,
        }
        resp = client.post("/api/dataclean/outliers", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "outliers" in data or "indices" in data or "mask" in data

    def test_outliers_iqr(self, client):
        """POST /api/dataclean/outliers with IQR method."""
        payload = {
            "data": [1.0, 1.1, 1.0, 0.9, 1.0, 1.1, 5.0, 1.0, 0.9],
            "method": "iqr",
        }
        resp = client.post("/api/dataclean/outliers", json=payload)
        assert resp.status_code == 200

    def test_outliers_mad(self, client):
        """POST /api/dataclean/outliers with MAD method."""
        payload = {
            "data": [1.0, 1.1, 1.0, 0.9, 1.0],
            "method": "mad",
        }
        resp = client.post("/api/dataclean/outliers", json=payload)
        assert resp.status_code == 200

    def test_outliers_too_short(self, client):
        """POST /api/dataclean/outliers with < 3 data points returns 422."""
        payload = {"data": [1.0, 2.0], "method": "3sigma"}
        resp = client.post("/api/dataclean/outliers", json=payload)
        assert resp.status_code == 422

    def test_outliers_invalid_method(self, client):
        """POST /api/dataclean/outliers with invalid method returns 422."""
        payload = {"data": [1.0, 2.0, 3.0], "method": "unknown"}
        resp = client.post("/api/dataclean/outliers", json=payload)
        assert resp.status_code == 422

    def test_interpolate_linear(self, client):
        """POST /api/dataclean/interpolate with linear method fills gaps."""
        payload = {
            "data": [1.0, None, None, 4.0, 5.0],
            "method": "linear",
        }
        resp = client.post("/api/dataclean/interpolate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "cleaned" in data or "data" in data or isinstance(data, list)

    def test_interpolate_spline(self, client):
        """POST /api/dataclean/interpolate with spline method."""
        payload = {
            "data": [1.0, None, 3.0, None, 5.0],
            "method": "spline",
        }
        resp = client.post("/api/dataclean/interpolate", json=payload)
        assert resp.status_code == 200

    def test_interpolate_too_short(self, client):
        """POST /api/dataclean/interpolate with < 2 points returns 422."""
        payload = {"data": [1.0], "method": "linear"}
        resp = client.post("/api/dataclean/interpolate", json=payload)
        assert resp.status_code == 422
