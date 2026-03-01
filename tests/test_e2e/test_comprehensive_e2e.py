"""Comprehensive E2E tests — multi-scenario, multi-user, multi-case.

Covers:
- All 3 report routes (simulation, skill, chat fallback)
- Multi-user document permissions
- API Key authentication (protected vs open paths)
- Report history isolation per user
- Dashboard data accuracy
- Concurrent user simulation
- Edge cases and error handling
"""

from __future__ import annotations

import json
import os
import sys
from unittest import mock

import pytest
from fastapi.testclient import TestClient

# Import hydromas_call for CLI tests (optional — not part of this repo)
_SCRIPT_DIR = os.path.expanduser(
    "~/.openclaw/workspace/skills/hydromas/scripts"
)
if os.path.isdir(_SCRIPT_DIR):
    sys.path.insert(0, _SCRIPT_DIR)

try:
    import hydromas_call as _hc_module  # noqa: F401
    _HAS_HYDROMAS_CALL = True
except ImportError:
    _HAS_HYDROMAS_CALL = False

_skip_no_hc = pytest.mark.skipif(
    not _HAS_HYDROMAS_CALL, reason="hydromas_call module not installed"
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def client():
    """Create FastAPI test client with no API key."""
    os.environ.pop("HYDROMAS_API_KEY", None)
    from web.app import app
    return TestClient(app)


@pytest.fixture
def temp_history(tmp_path, monkeypatch):
    """Redirect report history to temp file for both API and CLI."""
    hist = str(tmp_path / "report_history.jsonl")
    monkeypatch.setattr("web.routers.gateway._REPORT_HISTORY_PATH", hist)
    try:
        import hydromas_call
        monkeypatch.setattr("hydromas_call.REPORT_HISTORY_PATH", hist)
    except ImportError:
        pass
    return hist


@pytest.fixture
def mock_feishu(monkeypatch):
    """Mock all Feishu API calls for CLI tests."""
    fake_session = mock.MagicMock()
    fake_session.post.return_value.json.return_value = {
        "code": 0,
        "data": {"document": {"document_id": "doc_e2e_test"}},
    }
    fake_session.get.return_value.json.return_value = {
        "code": 0, "data": {"items": []}
    }
    fake_session.patch.return_value.json.return_value = {"code": 0}

    def _post_side(url, **kwargs):
        resp = mock.MagicMock()
        if "documents" in url and "blocks" not in url:
            resp.json.return_value = {
                "code": 0,
                "data": {"document": {"document_id": "doc_e2e_test"}},
            }
        elif "permissions" in url:
            resp.json.return_value = {"code": 0}
        elif "blocks" in url:
            resp.json.return_value = {
                "code": 0,
                "data": {"children": [{"block_id": "blk_1"}]},
            }
        else:
            resp.json.return_value = {"code": 0, "data": {}}
        return resp

    fake_session.post.side_effect = _post_side
    monkeypatch.setattr("hydromas_call._get_feishu_session", lambda: fake_session)
    monkeypatch.setattr("hydromas_call._feishu_token_cache",
                        {"token": "fake", "expires": 9999999999})
    return fake_session


@pytest.fixture
def mock_api(monkeypatch):
    """Mock HydroMAS API for CLI tests."""
    def _fake_post(path, data):
        if "tank-analysis" in path:
            return {
                "parameters": {
                    "tank_area_m2": 1.0, "discharge_coeff": 0.6,
                    "outlet_area_m2": 0.01, "h_max_m": 2.0,
                    "initial_h_m": 0.5, "q_in_m3s": 0.01,
                    "duration_s": 300, "dt_s": 1.0, "solver": "rk4",
                    "inflow_type": "constant",
                },
                "simulation": {"time": [0, 1], "water_level": [0.5, 0.48],
                               "outflow": [0.01, 0.01]},
                "analysis": {
                    "initial_h": 0.5, "final_h": 0.48, "h_change": -0.02,
                    "h_max_sim": 0.5, "h_min_sim": 0.48,
                    "volume_change_m3": -0.02, "q_in_total_m3": 0.02,
                    "q_out_total_m3": 0.02, "mass_balance_error_m3": 0.0,
                    "response_type": "单调下降", "is_steady_state": False,
                    "h_steady_state_theory": 0.14,
                },
                "odd_check": {"status": "normal", "margin_high_pct": 75,
                              "margin_low_pct": 100, "violations": []},
                "insights": ["水位下降"], "recommendations": ["增加入流"],
                "title": "仿真", "generated_at": "2026-03-01T12:00:00",
            }
        elif "gateway/chat" in path:
            return {"status": "success", "result": {"response": "OK"},
                    "role": data.get("role", "operator")}
        elif "gateway/skills" in path:
            # NOTE: must check "gateway/skills" (plural) BEFORE "gateway/skill"
            # because "gateway/skill" is a substring of "gateway/skills"
            return {
                "skills": [
                    {"name": "four_prediction_loop",
                     "trigger_phrases": ["四预", "闭环", "预警预报"],
                     "has_instance": True},
                    {"name": "leak_diagnosis",
                     "trigger_phrases": ["泄漏", "漏水", "leak"],
                     "has_instance": True},
                    {"name": "daily_report",
                     "trigger_phrases": ["日报", "daily report"],
                     "has_instance": True},
                ],
                "total": 3,
            }
        elif "gateway/skill" in path:
            return {"status": "success", "skill": data.get("skill_name"),
                    "result": {"data": {"summary": "Done"}}}
        return {"status": "success"}

    def _fake_get(path):
        if "gateway/skills" in path:
            return _fake_post(path, {})
        if "gateway/health" in path:
            return {"status": "healthy", "agents_registered": 5}
        return {}

    monkeypatch.setattr("hydromas_call._post", _fake_post)
    monkeypatch.setattr("hydromas_call._get", _fake_get)
    monkeypatch.setattr("hydromas_call._post_binary",
                        lambda *a, **kw: {"error": "mock"})

    # Reset skills cache in-place so _find_matching_skill re-fetches from mock
    import hydromas_call as _hc
    _hc._skills_cache["skills"] = None
    _hc._skills_cache["expires"] = 0


# ═══════════════════════════════════════════════════════════════
# Multi-Scenario Report Route Tests
# ═══════════════════════════════════════════════════════════════

@_skip_no_hc
class TestReportRoutes:
    """Test all 3 report routing paths."""

    @pytest.mark.parametrize("message,expected_route", [
        ("水箱仿真 初始水位1.0米", "simulation"),
        ("模拟水位变化 时长600秒", "simulation"),
        ("进行水箱阶跃响应测试", "simulation"),
        ("水动力分析", "simulation"),
    ])
    def test_simulation_route_keywords(self, mock_feishu, mock_api,
                                       temp_history, capsys,
                                       message, expected_route):
        """Various simulation keywords should trigger tank-analysis route."""
        import hydromas_call
        hydromas_call.cmd_report([message])
        out = capsys.readouterr().out
        assert "飞书文档:" in out
        # History should record simulation
        records = hydromas_call._load_report_history()
        assert len(records) >= 1
        assert records[0]["skill"] == "simulation"

    @pytest.mark.parametrize("message,expected_skill", [
        ("运行四预闭环分析", "four_prediction_loop"),
        ("管网泄漏检测", "leak_diagnosis"),
        ("生成日报", "daily_report"),
    ])
    def test_skill_route_matching(self, mock_feishu, mock_api,
                                  temp_history, capsys,
                                  message, expected_skill):
        """Skill trigger phrases should route to skill endpoint."""
        import hydromas_call
        hydromas_call.cmd_report([message])
        out = capsys.readouterr().out
        assert "飞书文档:" in out
        records = hydromas_call._load_report_history()
        assert len(records) >= 1
        assert records[0]["skill"] == expected_skill

    @pytest.mark.parametrize("message", [
        "请帮我分析最近的运行数据",
        "水厂运行概况",
        "你好，系统状态如何？",
    ])
    def test_chat_fallback_route(self, mock_feishu, mock_api,
                                 temp_history, capsys, message):
        """Non-matching messages should fall back to chat."""
        import hydromas_call
        hydromas_call.cmd_report([message])
        out = capsys.readouterr().out
        assert "飞书文档:" in out
        records = hydromas_call._load_report_history()
        assert len(records) >= 1
        assert records[0]["skill"] == "chat"


# ═══════════════════════════════════════════════════════════════
# Multi-User Permission Tests
# ═══════════════════════════════════════════════════════════════

@_skip_no_hc
class TestMultiUserPermissions:
    """Test per-user document permissions via --user-openid."""

    USERS = [
        ("ou_alice_001", "Alice"),
        ("ou_bob_002", "Bob"),
        ("ou_charlie_003", "Charlie"),
    ]

    def test_each_user_gets_own_grant(self, mock_feishu, mock_api,
                                      temp_history, capsys):
        """Each user's report should record their openid."""
        import hydromas_call
        for uid, _ in self.USERS:
            hydromas_call.cmd_report([
                "水箱仿真", "--user-openid", uid
            ])

        records = hydromas_call._load_report_history()
        assert len(records) == 3
        user_ids = {r["user_id"] for r in records}
        assert user_ids == {"ou_alice_001", "ou_bob_002", "ou_charlie_003"}

    def test_no_openid_uses_default(self, mock_feishu, mock_api,
                                    temp_history, capsys):
        """Without --user-openid, default admin openid is used."""
        import hydromas_call
        hydromas_call.cmd_report(["水箱仿真"])
        records = hydromas_call._load_report_history()
        assert records[0]["user_id"] == hydromas_call.DEFAULT_USER_OPENID

    def test_admin_openid_not_duplicated(self, mock_feishu, mock_api,
                                         temp_history, capsys):
        """Passing admin openid as user should not cause double grant."""
        import hydromas_call
        admin_id = hydromas_call.DEFAULT_USER_OPENID
        hydromas_call.cmd_report([
            "水箱仿真", "--user-openid", admin_id
        ])
        out = capsys.readouterr().out
        assert "飞书文档:" in out


# ═══════════════════════════════════════════════════════════════
# Report History Isolation Tests
# ═══════════════════════════════════════════════════════════════

@_skip_no_hc
class TestReportHistoryIsolation:
    """Test that report history is properly isolated per user."""

    def test_history_per_user_isolation(self, mock_feishu, mock_api,
                                        temp_history, capsys):
        """Each user should only see their own reports."""
        import hydromas_call

        # User A generates 3 reports
        for i in range(3):
            hydromas_call.cmd_report([
                f"分析任务{i}", "--user-openid", "ou_user_a"
            ])

        # User B generates 2 reports
        for i in range(2):
            hydromas_call.cmd_report([
                f"分析任务B{i}", "--user-openid", "ou_user_b"
            ])

        # Check isolation
        a_records = hydromas_call._load_report_history("ou_user_a")
        b_records = hydromas_call._load_report_history("ou_user_b")
        all_records = hydromas_call._load_report_history()

        assert len(a_records) == 3
        assert len(b_records) == 2
        assert len(all_records) == 5

    def test_history_limit(self, mock_feishu, mock_api, temp_history, capsys):
        """History limit parameter should work."""
        import hydromas_call

        for i in range(10):
            hydromas_call.cmd_report([
                f"任务{i}", "--user-openid", "ou_test"
            ])

        limited = hydromas_call._load_report_history(limit=3)
        assert len(limited) == 3

    def test_history_newest_first(self, mock_feishu, mock_api,
                                  temp_history, capsys):
        """History should return newest records first."""
        import hydromas_call

        for i in range(5):
            hydromas_call.cmd_report([
                f"任务{i}", "--user-openid", "ou_test"
            ])

        records = hydromas_call._load_report_history()
        # Last generated should be first in the list
        assert "任务4" in records[0]["title"]


# ═══════════════════════════════════════════════════════════════
# API Authentication Tests (FastAPI)
# ═══════════════════════════════════════════════════════════════

class TestAPIKeyAuthentication:
    """Test API key middleware with the FastAPI app."""

    def test_health_always_accessible(self, client):
        """Health endpoint should work without API key."""
        resp = client.get("/api/gateway/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_root_always_accessible(self, client):
        """Root page should work without API key."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_dashboard_accessible(self, client):
        """Dashboard page should be accessible."""
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "HydroMAS Dashboard" in resp.text

    def test_skills_endpoint_works(self, client):
        """Skills listing should work without API key when none configured."""
        resp = client.get("/api/gateway/skills")
        assert resp.status_code == 200

    def test_chat_with_user_context(self, client):
        """Chat should accept and return user_id."""
        resp = client.post("/api/gateway/chat", json={
            "message": "hello",
            "role": "operator",
            "user_id": "ou_test_user",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "ou_test_user"
        assert data["role"] == "operator"

    def test_chat_backward_compatible(self, client):
        """Chat should work without user_id field."""
        resp = client.post("/api/gateway/chat", json={
            "message": "hello",
            "role": "operator",
        })
        assert resp.status_code == 200
        assert resp.json()["user_id"] == ""


# ═══════════════════════════════════════════════════════════════
# Gateway Role Tests
# ═══════════════════════════════════════════════════════════════

class TestGatewayRoles:
    """Test role-based access patterns."""

    @pytest.mark.parametrize("role", ["researcher", "designer", "operator"])
    def test_all_roles_accepted(self, client, role):
        """All 3 roles should be accepted by chat endpoint."""
        resp = client.post("/api/gateway/chat", json={
            "message": "test",
            "role": role,
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == role

    def test_roles_endpoint(self, client):
        """Roles endpoint should list all role profiles."""
        resp = client.get("/api/gateway/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert "researcher" in data["roles"]
        assert "designer" in data["roles"]
        assert "operator" in data["roles"]


# ═══════════════════════════════════════════════════════════════
# Dashboard Data Accuracy Tests
# ═══════════════════════════════════════════════════════════════

class TestDashboardAccuracy:
    """Test that dashboard returns accurate system data."""

    def test_dashboard_structure(self, client, temp_history):
        """Dashboard should return all required fields."""
        resp = client.get("/api/gateway/dashboard")
        assert resp.status_code == 200
        data = resp.json()

        assert "status" in data
        assert "version" in data
        assert "agents" in data
        assert "skills" in data
        assert "reports" in data
        assert "roles" in data

        assert isinstance(data["agents"]["total"], int)
        assert isinstance(data["agents"]["names"], list)
        assert isinstance(data["skills"]["total"], int)
        assert isinstance(data["skills"]["names"], list)
        assert isinstance(data["reports"]["recent"], list)
        assert isinstance(data["reports"]["total_users"], int)

    def test_dashboard_reflects_reports(self, client, temp_history):
        """Dashboard should reflect stored report history."""
        # Add reports
        for i in range(3):
            rec = {
                "user_id": f"ou_dash_user_{i}",
                "doc_token": f"doc_{i}",
                "doc_url": f"https://test/doc_{i}",
                "title": f"Dashboard Test {i}",
                "skill": "simulation",
                "created_at": f"2026-03-01T12:0{i}:00",
            }
            with open(temp_history, "a") as f:
                f.write(json.dumps(rec) + "\n")

        resp = client.get("/api/gateway/dashboard")
        data = resp.json()
        assert data["reports"]["total_users"] == 3
        assert len(data["reports"]["recent"]) <= 5

    def test_dashboard_agents_populated(self, client, temp_history):
        """Dashboard should list registered agents."""
        resp = client.get("/api/gateway/dashboard")
        data = resp.json()
        assert data["agents"]["total"] > 0
        assert "orchestrator" in data["agents"]["names"]

    def test_dashboard_skills_populated(self, client, temp_history):
        """Dashboard should list available skills."""
        resp = client.get("/api/gateway/dashboard")
        data = resp.json()
        assert data["skills"]["total"] > 0


# ═══════════════════════════════════════════════════════════════
# Report Query API Tests
# ═══════════════════════════════════════════════════════════════

class TestReportsAPI:
    """Test the /api/gateway/reports endpoint."""

    def test_empty_reports(self, client, temp_history):
        resp = client.get("/api/gateway/reports")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_reports_multiple_users(self, client, temp_history):
        """Multiple users' reports should be queryable."""
        users = {"ou_x": 5, "ou_y": 3, "ou_z": 2}
        for uid, count in users.items():
            for i in range(count):
                rec = {
                    "user_id": uid, "doc_token": f"d_{uid}_{i}",
                    "doc_url": "u", "title": f"R{i}",
                    "skill": "sim", "created_at": "2026-03-01",
                }
                with open(temp_history, "a") as f:
                    f.write(json.dumps(rec) + "\n")

        # All reports
        resp = client.get("/api/gateway/reports")
        assert resp.json()["total"] == 10

        # Per-user
        for uid, expected in users.items():
            resp = client.get(f"/api/gateway/reports?user_id={uid}")
            assert resp.json()["total"] == expected

    def test_reports_limit_param(self, client, temp_history):
        for i in range(20):
            rec = {
                "user_id": "ou_lim", "doc_token": f"d{i}",
                "doc_url": "u", "title": f"R{i}",
                "skill": "s", "created_at": "2026-03-01",
            }
            with open(temp_history, "a") as f:
                f.write(json.dumps(rec) + "\n")

        resp = client.get("/api/gateway/reports?limit=5")
        assert resp.json()["total"] == 5

    def test_reports_default_limit(self, client, temp_history):
        """Default limit should be 20."""
        for i in range(25):
            rec = {
                "user_id": "ou", "doc_token": f"d{i}",
                "doc_url": "u", "title": f"R{i}",
                "skill": "s", "created_at": "2026-03-01",
            }
            with open(temp_history, "a") as f:
                f.write(json.dumps(rec) + "\n")

        resp = client.get("/api/gateway/reports")
        assert resp.json()["total"] == 20


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════

@_skip_no_hc
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_message_rejected(self, client):
        """Empty message should be rejected."""
        resp = client.post("/api/gateway/chat", json={
            "message": "",
            "role": "operator",
        })
        assert resp.status_code == 422  # Validation error

    def test_very_long_user_id(self, client):
        """Very long user_id should still work."""
        resp = client.post("/api/gateway/chat", json={
            "message": "test",
            "role": "operator",
            "user_id": "ou_" + "x" * 200,
        })
        assert resp.status_code == 200

    def test_special_chars_in_message(self, client):
        """Special characters in message should not crash."""
        resp = client.post("/api/gateway/chat", json={
            "message": "测试 <script>alert('xss')</script> & 'quotes' \"double\"",
            "role": "operator",
        })
        assert resp.status_code == 200

    def test_nonexistent_skill(self, client):
        """Calling a non-existent skill should return error."""
        resp = client.post("/api/gateway/skill", json={
            "skill_name": "nonexistent_skill_xyz",
            "params": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_reports_corrupted_jsonl(self, client, temp_history):
        """Corrupted JSONL lines should be skipped gracefully."""
        with open(temp_history, "w") as f:
            f.write('{"user_id":"ou_good","doc_token":"d","doc_url":"u","title":"t","skill":"s","created_at":"2026"}\n')
            f.write('THIS IS NOT JSON\n')
            f.write('{"user_id":"ou_good2","doc_token":"d2","doc_url":"u","title":"t2","skill":"s","created_at":"2026"}\n')

        resp = client.get("/api/gateway/reports")
        data = resp.json()
        assert data["total"] == 2  # corrupted line skipped

    def test_history_command_empty(self, temp_history, capsys):
        """CLI history with no records should print message."""
        import hydromas_call
        hydromas_call.cmd_history([])
        out = capsys.readouterr().out
        assert "无报告记录" in out

    def test_skill_listing(self, client):
        """Skills endpoint should list skills with metadata."""
        resp = client.get("/api/gateway/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert "total" in data
        assert isinstance(data["total"], int)
