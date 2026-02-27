"""Phase 3 tests for the water balance API router.
Phase 3 水平衡 API 路由测试。

Tests cover POST /api/water-balance/calc, invalid request handling,
POST /api/water-balance/anomaly, and empty residuals.
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


class TestWaterBalanceRouter:
    """Test /api/water-balance endpoints."""

    def test_calc_balance_endpoint(self, client):
        """POST /api/water-balance/calc with valid data returns balance result."""
        payload = {
            "nodes_data": [
                {"node_id": "intake", "node_type": "intake", "q_in": 0.05, "q_out": 0.05},
                {
                    "node_id": "pool_A", "node_type": "pool",
                    "q_in": 0.05, "q_out": 0.04,
                    "q_evap": 0.005, "q_loss": 0.005,
                },
            ],
            "edges_data": [["intake", "pool_A"]],
        }
        resp = client.post("/api/water-balance/calc", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "node_residuals" in data or "total_intake" in data or "balance_error" in data

    def test_calc_balance_invalid(self, client):
        """POST /api/water-balance/calc with missing data returns 422."""
        # Missing required edges_data field
        resp = client.post("/api/water-balance/calc", json={"nodes_data": []})
        assert resp.status_code == 422

    def test_detect_anomaly_endpoint(self, client):
        """POST /api/water-balance/anomaly with residuals returns result."""
        payload = {
            "residuals": {"node_A": 0.05, "node_B": 0.001, "node_C": 0.08},
            "threshold": 0.03,
        }
        resp = client.post("/api/water-balance/anomaly", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data
        assert "n_anomalies" in data
        # node_A and node_C exceed threshold 0.03
        assert data["n_anomalies"] >= 1

    def test_detect_anomaly_empty(self, client):
        """POST /api/water-balance/anomaly with empty residuals returns zero anomalies."""
        payload = {"residuals": {}, "threshold": 0.03}
        resp = client.post("/api/water-balance/anomaly", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["n_anomalies"] == 0
        assert data["anomalies"] == []
