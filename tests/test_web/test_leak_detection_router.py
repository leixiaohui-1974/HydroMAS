"""Phase 3 tests for the leak detection API router.
Phase 3 泄漏检测 API 路由测试。

Tests cover POST /api/leak-detection/detect, invalid request handling,
POST /api/leak-detection/localize, and result structure validation.
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


def _sample_graph_nodes():
    """Return minimal graph nodes for leak detection."""
    return [
        {"id": "N1", "features": [0.05, 0.3, 0.001]},
        {"id": "N2", "features": [0.04, 0.28, 0.002]},
        {"id": "N3", "features": [0.03, 0.25, 0.05]},
    ]


def _sample_graph_edges():
    """Return minimal graph edges for leak detection."""
    return [
        {"source": "N1", "target": "N2", "features": [100, 0.3, 1]},
        {"source": "N2", "target": "N3", "features": [80, 0.25, 1]},
    ]


class TestLeakDetectionRouter:
    """Test /api/leak-detection endpoints."""

    def test_detect_leak_endpoint(self, client):
        """POST /api/leak-detection/detect with valid data returns detection result."""
        payload = {
            "graph_nodes": _sample_graph_nodes(),
            "graph_edges": _sample_graph_edges(),
            "threshold": 0.95,
        }
        resp = client.post("/api/leak-detection/detect", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "leak_detected" in data
        assert "anomaly_scores" in data
        assert isinstance(data["leak_detected"], bool)

    def test_detect_leak_invalid(self, client):
        """POST /api/leak-detection/detect with missing graph_edges returns 422."""
        payload = {
            "graph_nodes": _sample_graph_nodes(),
            # graph_edges is missing
        }
        resp = client.post("/api/leak-detection/detect", json=payload)
        assert resp.status_code == 422

    def test_localize_leak_endpoint(self, client):
        """POST /api/leak-detection/localize returns suspects list."""
        payload = {
            "graph_data": {
                "nodes": _sample_graph_nodes(),
                "edges": _sample_graph_edges(),
                "adjacency": {"N1": ["N2"], "N2": ["N1", "N3"], "N3": ["N2"]},
            },
            "anomaly_scores": {"N1": 0.2, "N2": 0.5, "N3": 0.9},
            "top_k": 2,
        }
        resp = client.post("/api/leak-detection/localize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "suspects" in data
        assert "n_suspects" in data

    def test_detect_leak_result_has_max_score(self, client):
        """Detection result should contain max_score key."""
        payload = {
            "graph_nodes": _sample_graph_nodes(),
            "graph_edges": _sample_graph_edges(),
            "threshold": 0.5,
        }
        resp = client.post("/api/leak-detection/detect", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "max_score" in data
        assert isinstance(data["max_score"], (int, float))
