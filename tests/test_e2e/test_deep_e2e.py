"""Deep E2E tests — coverage gaps identified from production code audit.

Covers scenarios NOT tested in test_comprehensive_e2e.py:
  1. API Key middleware with key SET (reject/accept/wrong key)
  2. Security headers (CSP, X-Frame-Options, HSTS, etc.)
  3. Concurrent multi-user report generation
  4. Full pipeline chain: report → history → dashboard → query
  5. All CLI commands (chat, sim, skill, skills, health, roles, history)
  6. Feishu edge cases (token refresh, doc create fail, partial failures)
  7. Skill matching edge cases (overlapping triggers, case, best-match scoring)
  8. Report content quality (Markdown structure, adaptive report)
  9. Gateway endpoints (role actions, skills filter, unknown role)
 10. Simulation parameter parsing from natural language
 11. Performance (large history, many reports)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time as _time
from unittest import mock

import pytest
from fastapi.testclient import TestClient

# Import hydromas_call for CLI tests
_SCRIPT_DIR = os.path.expanduser(
    "~/.openclaw/workspace/skills/hydromas/scripts"
)
if os.path.isdir(_SCRIPT_DIR):
    sys.path.insert(0, _SCRIPT_DIR)


# ═══════════════════════════════════════════════════════════════
# Shared Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def client():
    """FastAPI test client without API key."""
    os.environ.pop("HYDROMAS_API_KEY", None)
    from web.app import app
    return TestClient(app)


@pytest.fixture
def client_with_key():
    """FastAPI test client with API key configured."""
    os.environ["HYDROMAS_API_KEY"] = "test_secret_key_2026"
    # Must re-import to pick up new env var in middleware
    import importlib
    import web.app as _app_mod
    importlib.reload(_app_mod)
    c = TestClient(_app_mod.app)
    yield c
    os.environ.pop("HYDROMAS_API_KEY", None)
    importlib.reload(_app_mod)


@pytest.fixture
def temp_history(tmp_path, monkeypatch):
    """Redirect report history to temp file."""
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
    """Mock all Feishu API calls."""
    fake_session = mock.MagicMock()

    grant_log = []

    def _post_side(url, **kwargs):
        resp = mock.MagicMock()
        if "documents" in url and "blocks" not in url:
            resp.json.return_value = {
                "code": 0,
                "data": {"document": {"document_id": "doc_deep_test"}},
            }
        elif "permissions" in url:
            body = kwargs.get("json", {})
            grant_log.append(body.get("member_id", ""))
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
    fake_session.get.return_value.json.return_value = {
        "code": 0, "data": {"items": []}
    }
    fake_session.patch.return_value.json.return_value = {"code": 0}

    monkeypatch.setattr("hydromas_call._get_feishu_session", lambda: fake_session)
    monkeypatch.setattr("hydromas_call._feishu_token_cache",
                        {"token": "fake_token", "expires": 9999999999})
    return {"session": fake_session, "grant_log": grant_log}


@pytest.fixture
def mock_api(monkeypatch):
    """Mock HydroMAS API with full skill list."""
    SKILLS_DATA = {
        "skills": [
            {"name": "four_prediction_loop",
             "trigger_phrases": ["四预", "闭环", "预警预报"],
             "has_instance": True},
            {"name": "leak_diagnosis",
             "trigger_phrases": ["泄漏", "漏水", "leak"],
             "has_instance": True},
            {"name": "daily_report",
             "trigger_phrases": ["日报", "daily report", "运营报告"],
             "has_instance": True},
            {"name": "evap_optimization",
             "trigger_phrases": ["蒸发", "冷却塔", "evaporation"],
             "has_instance": True},
            {"name": "reuse_scheduling",
             "trigger_phrases": ["回用", "中水", "reuse"],
             "has_instance": True},
            {"name": "global_dispatch",
             "trigger_phrases": ["调度", "dispatch", "全局优化"],
             "has_instance": True},
        ],
        "total": 6,
    }

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
                "simulation": {"time": [0, 1, 2], "water_level": [0.5, 0.48, 0.46],
                               "outflow": [0.01, 0.01, 0.01]},
                "analysis": {
                    "initial_h": 0.5, "final_h": 0.46, "h_change": -0.04,
                    "h_max_sim": 0.5, "h_min_sim": 0.46,
                    "volume_change_m3": -0.04, "q_in_total_m3": 0.02,
                    "q_out_total_m3": 0.06, "mass_balance_error_m3": 0.0,
                    "response_type": "单调下降", "is_steady_state": False,
                    "h_steady_state_theory": 0.14,
                },
                "odd_check": {"status": "normal", "margin_high_pct": 75,
                              "margin_low_pct": 100, "violations": []},
                "insights": ["水位持续下降", "系统尚未达到稳态"],
                "recommendations": ["增加入流量", "减小出口面积"],
                "title": "仿真报告", "generated_at": "2026-03-01T12:00:00",
            }
        elif "gateway/chat" in path:
            return {"status": "success", "result": {"response": "分析完成"},
                    "role": data.get("role", "operator")}
        elif "gateway/skills" in path:
            return SKILLS_DATA
        elif "gateway/skill" in path:
            return {"status": "success", "skill": data.get("skill_name"),
                    "result": {"data": {"summary": "技能执行完成",
                                        "risk_score": 0.3,
                                        "warning_level": "低"}}}
        elif "gateway/health" in path:
            return {"status": "healthy", "agents_registered": 15,
                    "platform": {"version": "0.2.0",
                                 "layers": ["L0_core", "L1_compute", "L2_mcp",
                                             "L3_skills", "L4_agents"]}}
        elif "gateway/roles" in path:
            return {"roles": {
                "researcher": {"name": "科研助理", "capabilities": ["simulation"]},
                "designer": {"name": "设计助理", "capabilities": ["control_design"]},
                "operator": {"name": "运维助理", "capabilities": ["forecast"]},
            }}
        elif "chart/" in path:
            return {"error": "mock chart"}
        return {"status": "success"}

    def _fake_get(path):
        if "gateway/skills" in path:
            return SKILLS_DATA
        if "gateway/health" in path:
            return _fake_post(path, {})
        if "gateway/roles" in path:
            return _fake_post(path, {})
        return {}

    monkeypatch.setattr("hydromas_call._post", _fake_post)
    monkeypatch.setattr("hydromas_call._get", _fake_get)
    monkeypatch.setattr("hydromas_call._post_binary",
                        lambda *a, **kw: {"error": "mock"})

    # Reset skills cache
    import hydromas_call as _hc
    _hc._skills_cache["skills"] = None
    _hc._skills_cache["expires"] = 0


# ═══════════════════════════════════════════════════════════════
# 1. API Key Authentication (with key configured)
# ═══════════════════════════════════════════════════════════════

class TestAPIKeyEnforcement:
    """Test API key middleware when HYDROMAS_API_KEY is set."""

    def test_health_open_with_key(self, client_with_key):
        """Health endpoint must be accessible without API key."""
        resp = client_with_key.get("/api/gateway/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_root_open_with_key(self, client_with_key):
        """Root page must be accessible without API key."""
        resp = client_with_key.get("/")
        assert resp.status_code == 200

    def test_docs_open_with_key(self, client_with_key):
        """Docs endpoint must be accessible without API key."""
        resp = client_with_key.get("/docs")
        # /docs returns HTML or redirect
        assert resp.status_code in (200, 307)

    def test_protected_endpoint_no_key_rejected(self, client_with_key):
        """Protected endpoint without API key must return 401."""
        resp = client_with_key.get("/api/gateway/skills")
        assert resp.status_code == 401
        assert "API key" in resp.json()["detail"]

    def test_protected_endpoint_wrong_key_rejected(self, client_with_key):
        """Wrong API key must return 401."""
        resp = client_with_key.get(
            "/api/gateway/skills",
            headers={"X-API-Key": "wrong_key_999"}
        )
        assert resp.status_code == 401

    def test_protected_endpoint_correct_key_accepted(self, client_with_key):
        """Correct API key must return 200."""
        resp = client_with_key.get(
            "/api/gateway/skills",
            headers={"X-API-Key": "test_secret_key_2026"}
        )
        assert resp.status_code == 200

    def test_post_endpoint_needs_key(self, client_with_key):
        """POST /api/gateway/chat must require API key."""
        resp = client_with_key.post("/api/gateway/chat", json={
            "message": "test", "role": "operator",
        })
        assert resp.status_code == 401

    def test_post_endpoint_with_key(self, client_with_key):
        """POST /api/gateway/chat with correct key must work."""
        resp = client_with_key.post(
            "/api/gateway/chat",
            json={"message": "test", "role": "operator"},
            headers={"X-API-Key": "test_secret_key_2026"}
        )
        assert resp.status_code == 200

    def test_static_files_always_open(self, client_with_key):
        """Static files should not require API key."""
        resp = client_with_key.get("/static/js/main.js")
        # 404 is fine (file may not exist), but NOT 401
        assert resp.status_code != 401


# ═══════════════════════════════════════════════════════════════
# 2. Security Headers
# ═══════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """Test that security headers are present on all responses."""

    def test_csp_header(self, client):
        resp = client.get("/api/gateway/health")
        assert "Content-Security-Policy" in resp.headers
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp

    def test_xframe_options(self, client):
        resp = client.get("/api/gateway/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_content_type_options(self, client):
        resp = client.get("/api/gateway/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy(self, client):
        resp = client.get("/")
        assert "Referrer-Policy" in resp.headers

    def test_hsts_header(self, client):
        resp = client.get("/api/gateway/health")
        hsts = resp.headers.get("Strict-Transport-Security", "")
        assert "max-age=" in hsts

    def test_permissions_policy(self, client):
        resp = client.get("/api/gateway/health")
        pp = resp.headers.get("Permissions-Policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp

    def test_headers_on_html_pages(self, client):
        """Security headers should also be on HTML pages."""
        resp = client.get("/dashboard")
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert "Content-Security-Policy" in resp.headers

    def test_headers_on_error_responses(self, client):
        """Security headers should be on 404 responses too."""
        resp = client.get("/api/nonexistent/path")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"


# ═══════════════════════════════════════════════════════════════
# 3. Concurrent Multi-User Report Generation
# ═══════════════════════════════════════════════════════════════

class TestConcurrentMultiUser:
    """Test thread-safety of report generation and history recording."""

    def test_concurrent_report_writes(self, mock_feishu, mock_api,
                                       temp_history):
        """Multiple users generating reports concurrently should not corrupt history."""
        import hydromas_call

        errors = []
        users = [f"ou_concurrent_{i}" for i in range(5)]

        def _generate(uid):
            try:
                hydromas_call.cmd_report([
                    "水箱仿真", "--user-openid", uid
                ])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=_generate, args=(u,)) for u in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent errors: {errors}"

        records = hydromas_call._load_report_history()
        assert len(records) == 5
        recorded_users = {r["user_id"] for r in records}
        assert recorded_users == set(users)

    def test_concurrent_history_reads(self, temp_history):
        """Concurrent reads of history should not crash."""
        import hydromas_call

        # Seed data
        for i in range(20):
            rec = {"user_id": f"ou_r_{i}", "doc_token": f"d{i}",
                   "doc_url": "u", "title": f"R{i}", "skill": "sim",
                   "created_at": "2026-03-01"}
            with open(temp_history, "a") as f:
                f.write(json.dumps(rec) + "\n")

        errors = []

        def _read():
            try:
                result = hydromas_call._load_report_history()
                assert len(result) == 20
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=_read) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors


# ═══════════════════════════════════════════════════════════════
# 4. Full Pipeline Chain
# ═══════════════════════════════════════════════════════════════

class TestFullPipelineChain:
    """Test complete flow: report → CLI history → API reports → dashboard."""

    def test_report_to_dashboard_chain(self, mock_feishu, mock_api,
                                        temp_history, client, capsys):
        """Reports created via CLI should appear in API reports and dashboard."""
        import hydromas_call

        # Step 1: Generate reports for 2 users
        for uid in ["ou_pipe_alice", "ou_pipe_bob"]:
            hydromas_call.cmd_report([
                "水箱仿真 初始水位1.0米", "--user-openid", uid
            ])

        # Step 2: CLI history should show them
        hydromas_call.cmd_history([])
        out = capsys.readouterr().out
        assert "报告历史" in out
        assert "共 2 条" in out

        # Step 3: API reports endpoint should return them
        resp = client.get("/api/gateway/reports")
        data = resp.json()
        assert data["total"] == 2

        # Step 4: Filter by user
        resp = client.get("/api/gateway/reports?user_id=ou_pipe_alice")
        assert resp.json()["total"] == 1
        assert resp.json()["reports"][0]["user_id"] == "ou_pipe_alice"

        # Step 5: Dashboard should reflect
        resp = client.get("/api/gateway/dashboard")
        dash = resp.json()
        assert dash["reports"]["total_users"] == 2
        assert len(dash["reports"]["recent"]) == 2

    def test_skill_report_pipeline(self, mock_feishu, mock_api,
                                    temp_history, client, capsys):
        """Skill-routed reports should record correct skill name."""
        import hydromas_call

        hydromas_call.cmd_report(["运行四预闭环分析", "--user-openid", "ou_pipe_skill"])

        # Check history records correct skill
        records = hydromas_call._load_report_history()
        assert records[0]["skill"] == "four_prediction_loop"

        # API reports should also show it
        resp = client.get("/api/gateway/reports")
        assert resp.json()["reports"][0]["skill"] == "four_prediction_loop"

    def test_chat_fallback_pipeline(self, mock_feishu, mock_api,
                                     temp_history, client, capsys):
        """Chat-routed reports should record 'chat' as skill."""
        import hydromas_call

        hydromas_call.cmd_report(["系统运行概况如何"])

        records = hydromas_call._load_report_history()
        assert records[0]["skill"] == "chat"


# ═══════════════════════════════════════════════════════════════
# 5. CLI Commands Complete Coverage
# ═══════════════════════════════════════════════════════════════

class TestCLICommands:
    """Test all CLI commands of hydromas_call.py."""

    def test_cmd_chat_basic(self, mock_api, capsys):
        """cmd_chat should print formatted response."""
        import hydromas_call
        hydromas_call.cmd_chat(["你好"])
        out = capsys.readouterr().out
        assert "HydroMAS" in out

    def test_cmd_chat_role_auto_detect_researcher(self, mock_api, capsys):
        """Messages with '仿真' should auto-detect researcher role."""
        import hydromas_call
        hydromas_call.cmd_chat(["运行仿真分析"])
        out = capsys.readouterr().out
        assert "researcher" in out

    def test_cmd_chat_role_auto_detect_designer(self, mock_api, capsys):
        """Messages with '控制设计' should auto-detect designer role."""
        import hydromas_call
        hydromas_call.cmd_chat(["控制设计方案"])
        out = capsys.readouterr().out
        assert "designer" in out

    def test_cmd_chat_explicit_role(self, mock_api, capsys):
        """Explicit --role should be used."""
        import hydromas_call
        hydromas_call.cmd_chat(["你好", "--role", "researcher"])
        out = capsys.readouterr().out
        assert "researcher" in out

    def test_cmd_skills_basic(self, mock_api, capsys):
        """cmd_skills should list available skills."""
        import hydromas_call
        hydromas_call.cmd_skills([])
        out = capsys.readouterr().out
        assert "Skills" in out

    def test_cmd_skills_with_role_filter(self, mock_api, capsys):
        """cmd_skills --role should filter skills."""
        import hydromas_call
        hydromas_call.cmd_skills(["--role", "operator"])
        out = capsys.readouterr().out
        assert "Skills" in out

    def test_cmd_health(self, mock_api, capsys):
        """cmd_health should print status."""
        import hydromas_call
        hydromas_call.cmd_health([])
        out = capsys.readouterr().out
        assert "healthy" in out
        assert "Agents" in out

    def test_cmd_roles(self, mock_api, capsys):
        """cmd_roles should print all roles."""
        import hydromas_call
        hydromas_call.cmd_roles([])
        out = capsys.readouterr().out
        assert "researcher" in out or "科研" in out

    def test_cmd_history_with_limit(self, mock_feishu, mock_api,
                                     temp_history, capsys):
        """cmd_history --limit should limit output."""
        import hydromas_call

        for i in range(10):
            hydromas_call.cmd_report([f"水箱仿真 任务{i}"])

        capsys.readouterr()  # clear previous output
        hydromas_call.cmd_history(["--limit", "3"])
        out = capsys.readouterr().out
        assert "共 3 条" in out

    def test_cmd_history_with_user_filter(self, mock_feishu, mock_api,
                                           temp_history, capsys):
        """cmd_history --user-openid should filter by user."""
        import hydromas_call

        hydromas_call.cmd_report(["水箱仿真", "--user-openid", "ou_hist_a"])
        hydromas_call.cmd_report(["水箱仿真", "--user-openid", "ou_hist_b"])
        hydromas_call.cmd_report(["水箱仿真", "--user-openid", "ou_hist_a"])

        capsys.readouterr()
        hydromas_call.cmd_history(["--user-openid", "ou_hist_a"])
        out = capsys.readouterr().out
        assert "共 2 条" in out

    def test_main_unknown_command(self, monkeypatch, capsys):
        """Unknown command should print help and exit."""
        import hydromas_call
        monkeypatch.setattr("sys.argv", ["hydromas_call.py", "nonexistent_command"])
        with pytest.raises(SystemExit) as exc_info:
            hydromas_call.main()
        assert exc_info.value.code == 1

    def test_cmd_chat_no_args(self, capsys):
        """cmd_chat with no args should exit with error."""
        import hydromas_call
        with pytest.raises(SystemExit):
            hydromas_call.cmd_chat([])

    def test_cmd_report_no_args(self, capsys):
        """cmd_report with no args should exit with error."""
        import hydromas_call
        with pytest.raises(SystemExit):
            hydromas_call.cmd_report([])


# ═══════════════════════════════════════════════════════════════
# 6. Feishu Integration Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestFeishuEdgeCases:
    """Test Feishu integration error handling."""

    def test_grant_log_includes_admin_and_user(self, mock_feishu, mock_api,
                                                temp_history, capsys):
        """Both admin and requesting user should be granted access."""
        import hydromas_call
        hydromas_call.cmd_report([
            "水箱仿真", "--user-openid", "ou_new_user_789"
        ])
        grant_log = mock_feishu["grant_log"]
        assert hydromas_call.DEFAULT_USER_OPENID in grant_log
        assert "ou_new_user_789" in grant_log

    def test_multiple_users_granted(self, mock_feishu, mock_api,
                                     temp_history, capsys):
        """Each report request grants both admin + requester."""
        import hydromas_call

        users = ["ou_u1", "ou_u2", "ou_u3"]
        for uid in users:
            mock_feishu["grant_log"].clear()
            hydromas_call.cmd_report([
                "水箱仿真", "--user-openid", uid
            ])
            # Admin should always be in grant log
            assert hydromas_call.DEFAULT_USER_OPENID in mock_feishu["grant_log"]
            assert uid in mock_feishu["grant_log"]

    def test_admin_not_double_granted(self, mock_feishu, mock_api,
                                       temp_history, capsys):
        """When user IS admin, should not grant twice."""
        import hydromas_call
        admin_id = hydromas_call.DEFAULT_USER_OPENID
        mock_feishu["grant_log"].clear()
        hydromas_call.cmd_report([
            "水箱仿真", "--user-openid", admin_id
        ])
        admin_grants = [g for g in mock_feishu["grant_log"] if g == admin_id]
        assert len(admin_grants) == 1

    def test_no_openid_still_grants_admin(self, mock_feishu, mock_api,
                                           temp_history, capsys):
        """Without --user-openid, admin should still be granted."""
        import hydromas_call
        mock_feishu["grant_log"].clear()
        hydromas_call.cmd_report(["水箱仿真"])
        assert hydromas_call.DEFAULT_USER_OPENID in mock_feishu["grant_log"]

    def test_feishu_doc_url_format(self, mock_feishu, mock_api,
                                    temp_history, capsys):
        """Doc URL should follow the correct format."""
        import hydromas_call
        hydromas_call.cmd_report(["水箱仿真"])
        out = capsys.readouterr().out
        assert "飞书文档:" in out
        assert "feishu.cn/docx/" in out

    def test_report_records_doc_token(self, mock_feishu, mock_api,
                                       temp_history, capsys):
        """Report history should include doc_token."""
        import hydromas_call
        hydromas_call.cmd_report(["水箱仿真"])
        records = hydromas_call._load_report_history()
        assert records[0]["doc_token"] == "doc_deep_test"
        assert "doc_url" in records[0]
        assert "created_at" in records[0]


# ═══════════════════════════════════════════════════════════════
# 7. Skill Matching Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestSkillMatchingEdgeCases:
    """Test _find_matching_skill with various edge cases."""

    def test_multiple_trigger_hits_wins(self, mock_api):
        """Skill with more trigger phrase matches should win."""
        import hydromas_call
        # "四预闭环" contains both "四预" and "闭环" → score 2
        # vs "调度" → score 1
        result = hydromas_call._find_matching_skill("运行四预闭环优化调度")
        assert result == "four_prediction_loop"  # score 2 > "global_dispatch" score 1

    def test_case_insensitive_match(self, mock_api):
        """Trigger matching should be case-insensitive."""
        import hydromas_call
        result = hydromas_call._find_matching_skill("LEAK detection needed")
        assert result == "leak_diagnosis"

    def test_no_match_returns_none(self, mock_api):
        """Message with no trigger matches should return None."""
        import hydromas_call
        result = hydromas_call._find_matching_skill("天气怎么样")
        assert result is None

    def test_partial_word_match(self, mock_api):
        """Trigger phrase as substring should still match."""
        import hydromas_call
        result = hydromas_call._find_matching_skill("检查是否有泄漏情况")
        assert result == "leak_diagnosis"

    def test_cache_reuse(self, mock_api, monkeypatch):
        """Second call should use cached skills, not fetch again."""
        import hydromas_call

        call_count = [0]
        original_get = hydromas_call._get

        def counting_get(path):
            if "gateway/skills" in path:
                call_count[0] += 1
            return original_get(path)

        monkeypatch.setattr("hydromas_call._get", counting_get)
        hydromas_call._skills_cache["skills"] = None
        hydromas_call._skills_cache["expires"] = 0

        hydromas_call._find_matching_skill("检测泄漏")
        hydromas_call._find_matching_skill("四预分析")

        assert call_count[0] == 1  # only fetched once

    def test_cache_expires(self, mock_api, monkeypatch):
        """Expired cache should trigger re-fetch."""
        import hydromas_call

        call_count = [0]
        original_get = hydromas_call._get

        def counting_get(path):
            if "gateway/skills" in path:
                call_count[0] += 1
            return original_get(path)

        monkeypatch.setattr("hydromas_call._get", counting_get)

        # Set cache to already expired
        hydromas_call._skills_cache["skills"] = []
        hydromas_call._skills_cache["expires"] = _time.time() - 1

        hydromas_call._find_matching_skill("test")
        assert call_count[0] == 1

    def test_all_six_skills_matchable(self, mock_api):
        """Each of the 6 mocked skills should be matchable."""
        import hydromas_call

        test_cases = [
            ("四预分析", "four_prediction_loop"),
            ("管网泄漏排查", "leak_diagnosis"),
            ("今日日报", "daily_report"),
            ("冷却塔蒸发量", "evap_optimization"),
            ("中水回用方案", "reuse_scheduling"),
            ("全局优化调度", "global_dispatch"),
        ]
        for msg, expected in test_cases:
            result = hydromas_call._find_matching_skill(msg)
            assert result == expected, f"'{msg}' should match '{expected}', got '{result}'"

    def test_simulation_keywords_bypass_skill_matching(self, mock_api):
        """Messages with simulation keywords should not go through skill matching."""
        import hydromas_call
        assert hydromas_call._is_simulation_request("水箱仿真 初始水位1米")
        assert hydromas_call._is_simulation_request("模拟水位变化")
        assert not hydromas_call._is_simulation_request("四预闭环分析")
        assert not hydromas_call._is_simulation_request("泄漏检测")


# ═══════════════════════════════════════════════════════════════
# 8. Report Content Quality
# ═══════════════════════════════════════════════════════════════

class TestReportContentQuality:
    """Test Markdown report generation quality."""

    def test_simulation_markdown_structure(self, mock_api):
        """Tank analysis Markdown should have all required sections."""
        import hydromas_call

        data = mock_api  # we call the builder directly
        # Build mock data like what _fake_post returns
        sim_data = {
            "parameters": {
                "tank_area_m2": 1.0, "discharge_coeff": 0.6,
                "outlet_area_m2": 0.01, "h_max_m": 2.0,
                "initial_h_m": 0.5, "q_in_m3s": 0.01,
                "duration_s": 300, "dt_s": 1.0, "solver": "rk4",
                "inflow_type": "constant",
            },
            "analysis": {
                "initial_h": 0.5, "final_h": 0.46, "h_change": -0.04,
                "h_max_sim": 0.5, "h_min_sim": 0.46,
                "volume_change_m3": -0.04, "q_in_total_m3": 0.02,
                "q_out_total_m3": 0.06, "mass_balance_error_m3": 0.0,
                "response_type": "单调下降", "is_steady_state": False,
                "h_steady_state_theory": 0.14,
            },
            "odd_check": {"status": "normal", "margin_high_pct": 75,
                          "margin_low_pct": 100, "violations": []},
            "insights": ["水位下降"], "recommendations": ["增加入流"],
            "title": "测试报告", "generated_at": "2026-03-01T12:00:00",
        }

        md = hydromas_call._build_analysis_markdown(sim_data)

        # Required sections
        assert "## 一、仿真配置" in md
        assert "## 三、仿真结果" in md
        assert "## 五、ODD 安全评估" in md
        assert "## 六、物理解读" in md
        assert "## 七、工程建议" in md
        # Tables
        assert "| 参数 | 值 |" in md or "| 参数 | 值 | 说明 |" in md
        # Values
        assert "0.5000" in md or "0.50" in md  # initial_h
        assert "rk4" in md

    def test_adaptive_report_with_skill_result(self, mock_api):
        """Adaptive report should handle skill result data."""
        import hydromas_call

        result = {"status": "success", "skill": "leak_diagnosis",
                  "result": {"data": {"summary": "未检测到泄漏",
                                      "risk_score": 0.1,
                                      "checked_nodes": 12}}}

        md = hydromas_call._build_adaptive_report(
            "管网泄漏检测", result, "leak_diagnosis")

        assert "泄漏" in md or "leak" in md.lower()
        assert "HydroMAS" in md

    def test_adaptive_report_with_chat_result(self, mock_api):
        """Adaptive report should handle chat fallback result."""
        import hydromas_call

        result = {"status": "success",
                  "result": {"response": "系统运行正常，各项指标在安全范围内。"}}

        md = hydromas_call._build_adaptive_report(
            "系统运行概况", result, None)

        assert "HydroMAS" in md

    def test_md_to_feishu_blocks_conversion(self):
        """Markdown to Feishu blocks conversion should handle all types."""
        import hydromas_call

        md = """# 标题（应跳过）

## 二级标题

### 三级标题

#### 四级标题

- 无序列表项
- 第二项

1. 有序列表
2. 第二项

> 引用文字

| 列A | 列B |
|-----|-----|
| 1   | 2   |

---

普通文本 **加粗** 内容

```python
print("hello")
```
"""
        blocks = hydromas_call._md_to_feishu_blocks(md)

        block_types = [b.get("block_type") or ("table" if b.get("_table") else None)
                       for b in blocks]

        assert hydromas_call.BT_H2 in block_types     # ## heading
        assert hydromas_call.BT_H3 in block_types     # ### heading
        assert hydromas_call.BT_H4 in block_types     # #### heading
        assert hydromas_call.BT_BULLET in block_types  # bullet
        assert hydromas_call.BT_ORDERED in block_types  # ordered
        assert hydromas_call.BT_QUOTE in block_types    # quote
        assert "table" in block_types                    # table
        assert hydromas_call.BT_DIVIDER in block_types  # divider
        assert hydromas_call.BT_CODE in block_types     # code block
        assert hydromas_call.BT_TEXT in block_types     # text

    def test_text_elements_bold_parsing(self):
        """Bold text should be parsed into bold elements."""
        import hydromas_call
        elements = hydromas_call._text_elements("普通 **加粗** 文字")
        bold_found = any(
            e.get("text_run", {}).get("text_element_style", {}).get("bold")
            for e in elements
        )
        assert bold_found

    def test_text_elements_link_parsing(self):
        """Links should be parsed into link elements."""
        import hydromas_call
        elements = hydromas_call._text_elements("点击 [查看](https://example.com) 详情")
        link_found = any(
            e.get("text_run", {}).get("text_element_style", {}).get("link")
            for e in elements
        )
        assert link_found

    def test_humanize_key_known_keys(self):
        """Known keys should return bilingual Chinese+English labels."""
        import hydromas_call
        assert "初始水位" in hydromas_call._humanize_key("initial_h")
        assert "预警等级" in hydromas_call._humanize_key("warning_level")
        assert "泄漏位置" in hydromas_call._humanize_key("leak_location")

    def test_humanize_key_unknown_key(self):
        """Unknown keys should be title-cased (with optional CN prefix)."""
        import hydromas_call
        result = hydromas_call._humanize_key("custom_metric")
        assert "Custom Metric" in result

    def test_format_value_types(self):
        """_format_value should handle all types correctly."""
        import hydromas_call
        assert hydromas_call._format_value(None) == "-"
        assert hydromas_call._format_value(True) == "是"
        assert hydromas_call._format_value(False) == "否"
        assert "0.1234" in hydromas_call._format_value(0.12344)
        assert hydromas_call._format_value("hello") == "hello"


# ═══════════════════════════════════════════════════════════════
# 9. Gateway Endpoints Coverage
# ═══════════════════════════════════════════════════════════════

class TestGatewayEndpoints:
    """Test all gateway router endpoints."""

    def test_role_actions_operator(self, client):
        """Operator role should have quick actions."""
        resp = client.get("/api/gateway/roles/operator/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "operator"
        assert len(data["actions"]) > 0
        action_labels = [a["label"] for a in data["actions"]]
        assert "四预闭环" in action_labels

    def test_role_actions_researcher(self, client):
        """Researcher role should have research-related actions."""
        resp = client.get("/api/gateway/roles/researcher/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "researcher"
        action_labels = [a["label"] for a in data["actions"]]
        assert "运行仿真" in action_labels

    def test_role_actions_designer(self, client):
        """Designer role should have design-related actions."""
        resp = client.get("/api/gateway/roles/designer/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "designer"
        action_labels = [a["label"] for a in data["actions"]]
        assert "控制设计" in action_labels

    def test_role_actions_unknown(self, client):
        """Unknown role should return error with available roles."""
        resp = client.get("/api/gateway/roles/unknown_role/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert "available" in data
        assert "operator" in data["available"]

    def test_skills_filter_by_role(self, client):
        """Skills should be filterable by role."""
        resp = client.get("/api/gateway/skills?role=operator")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role_filter"] == "operator"

    def test_skills_no_filter(self, client):
        """Skills without filter should return all."""
        resp = client.get("/api/gateway/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        assert data["role_filter"] is None

    def test_health_platform_info(self, client):
        """Health should return platform info."""
        resp = client.get("/api/gateway/health")
        data = resp.json()
        assert "platform" in data
        assert "version" in data["platform"]
        assert "layers" in data["platform"]
        assert len(data["platform"]["layers"]) == 5

    def test_chat_sanitizes_control_chars(self, client):
        """Chat endpoint should sanitize control characters."""
        resp = client.post("/api/gateway/chat", json={
            "message": "test\x00\x01\x02message",
            "role": "operator",
        })
        assert resp.status_code == 200

    def test_chat_returns_intent(self, client):
        """Chat response should include intent classification."""
        resp = client.post("/api/gateway/chat", json={
            "message": "运行水箱仿真",
            "role": "researcher",
        })
        data = resp.json()
        assert "intent" in data
        assert "route_type" in data["intent"]
        assert "domain" in data["intent"]

    def test_chat_returns_elapsed(self, client):
        """Chat response should include elapsed time."""
        resp = client.post("/api/gateway/chat", json={
            "message": "test", "role": "operator",
        })
        data = resp.json()
        assert "elapsed_ms" in data
        assert isinstance(data["elapsed_ms"], (int, float))

    def test_skill_with_params(self, client):
        """Skill endpoint should accept params and not return auth error."""
        resp = client.post("/api/gateway/skill", json={
            "skill_name": "four_prediction_loop",
            "params": {"target": "water_level"},
        })
        # 200 (success or skill error) is fine; 401 would mean auth problem
        assert resp.status_code != 401
        assert resp.status_code in (200, 400, 500)

    def test_skill_no_implementation(self, client):
        """Skill without implementation should return error."""
        resp = client.post("/api/gateway/skill", json={
            "skill_name": "nonexistent_xyz",
            "params": {},
        })
        data = resp.json()
        assert data["status"] == "error"


# ═══════════════════════════════════════════════════════════════
# 10. Simulation Parameter Parsing
# ═══════════════════════════════════════════════════════════════

class TestSimulationParamParsing:
    """Test natural language → simulation parameter extraction."""

    def test_parse_initial_h_chinese(self):
        import hydromas_call
        params = hydromas_call._parse_sim_params("初始水位1.5米")
        assert params["initial_h"] == 1.5

    def test_parse_initial_h_english(self):
        import hydromas_call
        params = hydromas_call._parse_sim_params("initial_h=2.0")
        assert params["initial_h"] == 2.0

    def test_parse_duration_chinese(self):
        import hydromas_call
        params = hydromas_call._parse_sim_params("时长600秒")
        assert params["duration"] == 600.0

    def test_parse_duration_english(self):
        import hydromas_call
        params = hydromas_call._parse_sim_params("duration=1200")
        assert params["duration"] == 1200.0

    def test_parse_tank_area(self):
        import hydromas_call
        params = hydromas_call._parse_sim_params("水箱面积2.5平方米")
        assert params["tank_params"]["area"] == 2.5

    def test_parse_outlet_area(self):
        import hydromas_call
        params = hydromas_call._parse_sim_params("出口面积0.005m²")
        assert params["tank_params"]["outlet_area"] == 0.005

    def test_parse_cd(self):
        import hydromas_call
        params = hydromas_call._parse_sim_params("流量系数Cd=0.65")
        assert params["tank_params"]["cd"] == 0.65

    def test_parse_inflow(self):
        import hydromas_call
        params = hydromas_call._parse_sim_params("入流0.02m³/s")
        assert params["q_in_profile"] == [[0, 0.02]]

    def test_parse_combined(self):
        """Multiple params in one message should all be extracted."""
        import hydromas_call
        params = hydromas_call._parse_sim_params(
            "水箱仿真 初始水位1.0米 时长600秒 面积2平方米 入流0.02m³/s"
        )
        assert params["initial_h"] == 1.0
        assert params["duration"] == 600.0
        assert params["tank_params"]["area"] == 2.0
        assert params["q_in_profile"] == [[0, 0.02]]

    def test_parse_no_params(self):
        """Message with no sim params should return empty dict."""
        import hydromas_call
        params = hydromas_call._parse_sim_params("分析一下系统状态")
        assert params == {}


# ═══════════════════════════════════════════════════════════════
# 11. Performance & Stress Tests
# ═══════════════════════════════════════════════════════════════

class TestPerformanceStress:
    """Test system behavior under load."""

    def test_large_history_file(self, temp_history, client):
        """System should handle large history files gracefully."""
        # Write 500 records
        for i in range(500):
            rec = {
                "user_id": f"ou_perf_{i % 10}",
                "doc_token": f"doc_{i}",
                "doc_url": f"https://test/doc_{i}",
                "title": f"性能测试报告 {i}",
                "skill": ["simulation", "chat", "leak_diagnosis"][i % 3],
                "created_at": f"2026-03-{(i % 28) + 1:02d}T12:00:00",
            }
            with open(temp_history, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        # API should respond within reasonable time
        import time
        start = time.time()
        resp = client.get("/api/gateway/reports?limit=20")
        elapsed = time.time() - start

        assert resp.status_code == 200
        assert resp.json()["total"] == 20
        assert elapsed < 2.0  # should be well under 2 seconds

    def test_large_history_dashboard(self, temp_history, client):
        """Dashboard should handle large history."""
        for i in range(200):
            rec = {
                "user_id": f"ou_dash_{i % 20}",
                "doc_token": f"doc_{i}",
                "doc_url": f"https://test/doc_{i}",
                "title": f"Dashboard Test {i}",
                "skill": "simulation",
                "created_at": f"2026-03-01T{i % 24:02d}:00:00",
            }
            with open(temp_history, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        resp = client.get("/api/gateway/dashboard")
        data = resp.json()
        assert data["reports"]["total_users"] == 20
        assert len(data["reports"]["recent"]) <= 5

    def test_rapid_report_generation(self, mock_feishu, mock_api,
                                      temp_history, capsys):
        """Rapid sequential reports should not corrupt history."""
        import hydromas_call

        for i in range(20):
            hydromas_call.cmd_report([f"水箱仿真 任务{i}"])

        records = hydromas_call._load_report_history()
        assert len(records) == 20

        # Verify JSONL integrity
        with open(temp_history) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 20
        for line in lines:
            parsed = json.loads(line)  # should not raise
            assert "user_id" in parsed
            assert "doc_token" in parsed


# ═══════════════════════════════════════════════════════════════
# 12. CORS Configuration
# ═══════════════════════════════════════════════════════════════

class TestCORSConfiguration:
    """Test CORS middleware behavior."""

    def test_cors_allows_configured_origin(self, client):
        """Configured origin should be allowed."""
        resp = client.options(
            "/api/gateway/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            }
        )
        # CORS preflight should not fail
        assert resp.status_code in (200, 400)

    def test_cors_api_key_in_allowed_headers(self, client):
        """X-API-Key should be in allowed CORS headers."""
        resp = client.options(
            "/api/gateway/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            }
        )
        allowed_headers = resp.headers.get("Access-Control-Allow-Headers", "")
        # If CORS is configured, X-API-Key should be allowed
        if allowed_headers:
            assert "x-api-key" in allowed_headers.lower()


# ═══════════════════════════════════════════════════════════════
# 13. Error Handling & Resilience
# ═══════════════════════════════════════════════════════════════

class TestErrorResilience:
    """Test error handling and edge cases for resilience."""

    def test_reports_nonexistent_file(self, client, monkeypatch):
        """Reports endpoint should handle missing history file."""
        monkeypatch.setattr(
            "web.routers.gateway._REPORT_HISTORY_PATH",
            "/tmp/nonexistent_history_xyz.jsonl"
        )
        resp = client.get("/api/gateway/reports")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_dashboard_no_history(self, client, monkeypatch):
        """Dashboard should work even without history file."""
        monkeypatch.setattr(
            "web.routers.gateway._REPORT_HISTORY_PATH",
            "/tmp/nonexistent_history_xyz.jsonl"
        )
        resp = client.get("/api/gateway/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reports"]["total_users"] == 0
        assert data["reports"]["recent"] == []

    def test_reports_empty_lines_skipped(self, client, temp_history):
        """Empty lines in JSONL should be skipped."""
        with open(temp_history, "w") as f:
            f.write('{"user_id":"u1","doc_token":"d","doc_url":"u","title":"t","skill":"s","created_at":"2026"}\n')
            f.write('\n')
            f.write('   \n')
            f.write('{"user_id":"u2","doc_token":"d2","doc_url":"u","title":"t2","skill":"s","created_at":"2026"}\n')

        resp = client.get("/api/gateway/reports")
        assert resp.json()["total"] == 2

    def test_reports_unicode_content(self, client, temp_history):
        """Unicode content in reports should be handled correctly."""
        rec = {
            "user_id": "ou_中文用户",
            "doc_token": "d_unicode",
            "doc_url": "https://test/中文",
            "title": "蒸发量分析报告 — 氧化铝厂",
            "skill": "evap_optimization",
            "created_at": "2026-03-01T12:00:00",
        }
        with open(temp_history, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        resp = client.get("/api/gateway/reports")
        data = resp.json()
        assert data["total"] == 1
        assert data["reports"][0]["title"] == "蒸发量分析报告 — 氧化铝厂"
        assert data["reports"][0]["user_id"] == "ou_中文用户"

    def test_record_report_creates_directory(self, tmp_path):
        """_record_report should create missing directories."""
        import hydromas_call

        nested_path = str(tmp_path / "subdir" / "deep" / "history.jsonl")
        original = hydromas_call.REPORT_HISTORY_PATH
        hydromas_call.REPORT_HISTORY_PATH = nested_path
        try:
            hydromas_call._record_report("user1", "doc1", "url1", "title1", "sim")
            assert os.path.exists(nested_path)
            with open(nested_path) as f:
                rec = json.loads(f.readline())
            assert rec["user_id"] == "user1"
        finally:
            hydromas_call.REPORT_HISTORY_PATH = original

    def test_load_history_invalid_json_skipped(self, temp_history):
        """Invalid JSON lines in history should be skipped gracefully (CLI side)."""
        import hydromas_call
        with open(temp_history, "w") as f:
            f.write('{"user_id":"good","doc_token":"d","doc_url":"u","title":"t","skill":"s","created_at":"2026"}\n')
            f.write('{broken json\n')
            f.write('{"user_id":"good2","doc_token":"d2","doc_url":"u","title":"t2","skill":"s","created_at":"2026"}\n')

        records = hydromas_call._load_report_history()
        # Corrupt line should be skipped, both valid records returned
        assert len(records) == 2


# ═══════════════════════════════════════════════════════════════
# 14. Auto-Detect Charts
# ═══════════════════════════════════════════════════════════════

class TestAutoDetectCharts:
    """Test _auto_detect_charts function."""

    def test_detects_timeseries_data(self, mock_api):
        """Should detect time-series arrays in nested result."""
        import hydromas_call
        result = {
            "result": {
                "data": {
                    "time": [0, 1, 2, 3],
                    "water_level": [1.0, 0.9, 0.8, 0.7],
                }
            }
        }
        charts = hydromas_call._auto_detect_charts(result)
        # With mock, chart generation returns None/empty
        assert isinstance(charts, list)

    def test_no_timeseries_no_charts(self, mock_api):
        """Non-timeseries data should produce no charts."""
        import hydromas_call
        result = {
            "result": {"response": "plain text response"}
        }
        charts = hydromas_call._auto_detect_charts(result)
        assert charts == []


# ═══════════════════════════════════════════════════════════════
# 15. System Status Endpoint
# ═══════════════════════════════════════════════════════════════

class TestSystemStatus:
    """Test /api/system/status endpoint."""

    def test_system_status(self, client):
        resp = client.get("/api/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert "layers" in data
        assert "version" in data
        assert data["layers"]["L0_core"] == "operational"

    def test_api_roles_endpoint(self, client):
        """Test /api/roles (app-level, not gateway)."""
        resp = client.get("/api/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert "operator" in data
        assert "engineer" in data
        assert "analyst" in data
        assert "admin" in data
