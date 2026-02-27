"""Phase 3 tests for the report API router.
Phase 3 报告 API 路由测试。

Tests cover POST /api/report/daily, invalid request handling,
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


class TestReportRouter:
    """Test /api/report endpoints."""

    def test_generate_daily_report_endpoint(self, client):
        """POST /api/report/daily with valid data returns report structure."""
        payload = {
            "date": "2026-02-27",
            "include_sections": ["balance", "anomaly", "kpi"],
        }
        resp = client.post("/api/report/daily", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert data["date"] == "2026-02-27"
        assert "sections" in data
        assert "balance" in data["sections"]
        assert "anomaly" in data["sections"]
        assert "kpi" in data["sections"]

    def test_generate_daily_report_invalid(self, client):
        """POST /api/report/daily with invalid date format returns 422."""
        payload = {
            "date": "not-a-date",  # Does not match YYYY-MM-DD pattern
            "include_sections": ["balance"],
        }
        resp = client.post("/api/report/daily", json=payload)
        assert resp.status_code == 422

    def test_generate_daily_report_all_sections(self, client):
        """POST /api/report/daily with all sections returns all section keys."""
        payload = {
            "date": "2026-01-15",
            "include_sections": ["balance", "anomaly", "kpi", "evaporation", "reuse"],
        }
        resp = client.post("/api/report/daily", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        sections = data["sections"]
        assert "balance" in sections
        assert "anomaly" in sections
        assert "kpi" in sections
        assert "evaporation" in sections
        assert "reuse" in sections

    def test_generate_daily_report_has_generated_at(self, client):
        """Report result should contain generated_at field."""
        payload = {
            "date": "2026-02-27",
            "include_sections": ["balance"],
        }
        resp = client.post("/api/report/daily", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "generated_at" in data
        # generated_at should be a date string
        assert isinstance(data["generated_at"], str)
        assert len(data["generated_at"]) == 10  # YYYY-MM-DD format
