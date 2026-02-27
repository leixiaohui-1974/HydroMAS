"""Phase 3 tests for the reuse water API router.
Phase 3 回用水 API 路由测试。

Tests cover POST /api/reuse/match, POST /api/reuse/optimize,
invalid request handling, and result structure validation.
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


class TestReuseRouter:
    """Test /api/reuse endpoints."""

    def test_match_reuse_endpoint(self, client):
        """POST /api/reuse/match with valid data returns matching result."""
        payload = {
            "source_quality": {"cod": 20, "turbidity": 3, "ph": 7.2},
            "target_requirements": [
                {"workshop_id": "WS_A", "max_cod": 30, "max_turbidity": 5, "demand_m3d": 100},
                {"workshop_id": "WS_B", "max_cod": 15, "max_turbidity": 2, "demand_m3d": 50},
            ],
        }
        resp = client.post("/api/reuse/match", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "matched_paths" in data
        assert "unmatched" in data
        assert "n_matched" in data
        assert "n_unmatched" in data
        # WS_A should match (cod 20 <= 30, turbidity 3 <= 5)
        # WS_B should not match (cod 20 > 15)
        assert data["n_matched"] == 1
        assert data["n_unmatched"] == 1

    def test_match_reuse_invalid(self, client):
        """POST /api/reuse/match with missing target_requirements returns 422."""
        payload = {
            "source_quality": {"cod": 20},
            # target_requirements is missing
        }
        resp = client.post("/api/reuse/match", json=payload)
        assert resp.status_code == 422

    def test_optimize_reuse_endpoint(self, client):
        """POST /api/reuse/optimize with valid data returns schedule."""
        payload = {
            "sources": [
                {"source_id": "S1", "capacity_m3d": 200, "cod": 15, "turbidity": 2},
            ],
            "demands": [
                {"workshop_id": "WS_A", "demand_m3d": 100, "max_cod": 30, "max_turbidity": 5},
            ],
            "constraints": {},
        }
        resp = client.post("/api/reuse/optimize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "schedule" in data
        assert "total_reuse_m3d" in data
        assert "reuse_rate" in data

    def test_match_reuse_result_has_source_quality(self, client):
        """Match result echoes back source_quality."""
        payload = {
            "source_quality": {"cod": 10, "turbidity": 1},
            "target_requirements": [
                {"workshop_id": "WS_X", "max_cod": 50, "max_turbidity": 10, "demand_m3d": 200},
            ],
        }
        resp = client.post("/api/reuse/match", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "source_quality" in data
        assert data["source_quality"]["cod"] == 10
