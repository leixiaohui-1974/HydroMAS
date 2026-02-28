"""Tests for the skills API router.
技能 API 路由测试。

Tests cover GET /api/skills/list, POST /api/skills/run,
POST /api/skills/four-prediction, POST /api/skills/lifecycle,
POST /api/skills/control-design, and report endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestSkillsRouter:
    """Test /api/skills endpoints."""

    def test_list_skills(self, client):
        """GET /api/skills/list returns skills array."""
        resp = client.get("/api/skills/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert isinstance(data["skills"], list)

    def test_four_prediction(self, client):
        """POST /api/skills/four-prediction runs the 四预 loop."""
        payload = {
            "water_level_data": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9],
            "risk_threshold": 0.7,
        }
        resp = client.post("/api/skills/four-prediction", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "steps_completed" in data

    def test_four_prediction_too_short(self, client):
        """POST /api/skills/four-prediction with < 2 data points returns 422."""
        payload = {"water_level_data": [1.0]}
        resp = client.post("/api/skills/four-prediction", json=payload)
        assert resp.status_code == 422

    def test_lifecycle(self, client):
        """POST /api/skills/lifecycle runs the full lifecycle skill."""
        resp = client.post("/api/skills/lifecycle", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data

    def test_control_design(self, client):
        """POST /api/skills/control-design runs the control design skill."""
        resp = client.post("/api/skills/control-design", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data

    def test_report_control(self, client):
        """POST /api/skills/report/control generates control report."""
        payload = {
            "results": {
                "controller_type": "PID",
                "setpoint": 1.0,
                "overshoot": 0.05,
                "settling_time": 30.0,
            }
        }
        resp = client.post("/api/skills/report/control", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "report_markdown" in data

    def test_report_odd(self, client):
        """POST /api/skills/report/odd generates ODD report."""
        payload = {
            "results": {
                "zone": "normal",
                "violations": [],
                "dimensions_checked": 6,
            }
        }
        resp = client.post("/api/skills/report/odd", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "report_markdown" in data

    def test_report_lifecycle(self, client):
        """POST /api/skills/report/lifecycle generates lifecycle report."""
        payload = {
            "results": {
                "stages": ["design", "build", "operate"],
                "overall_score": 85.0,
            }
        }
        resp = client.post("/api/skills/report/lifecycle", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "report_markdown" in data

    def test_report_missing_results(self, client):
        """POST /api/skills/report/* with missing results returns 422."""
        resp = client.post("/api/skills/report/control", json={})
        assert resp.status_code == 422
