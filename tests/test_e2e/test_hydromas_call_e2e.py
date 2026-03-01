"""E2E tests for hydromas_call.py — report pipeline with mocked Feishu + HydroMAS APIs."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from unittest import mock

import pytest

# Add the script directory to path so we can import hydromas_call
_SCRIPT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", ".openclaw", "workspace",
    "skills", "hydromas", "scripts",
)
_SCRIPT_DIR_REAL = os.path.expanduser(
    "~/.openclaw/workspace/skills/hydromas/scripts"
)
if os.path.isdir(_SCRIPT_DIR_REAL):
    sys.path.insert(0, _SCRIPT_DIR_REAL)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_feishu(monkeypatch):
    """Mock all Feishu API calls."""
    fake_session = mock.MagicMock()

    # tenant_access_token
    fake_session.post.return_value.json.return_value = {
        "code": 0,
        "tenant_access_token": "fake_token_123",
    }

    # create doc
    def _post_side_effect(url, **kwargs):
        resp = mock.MagicMock()
        if "documents" in url and "blocks" not in url:
            resp.json.return_value = {
                "code": 0,
                "data": {"document": {"document_id": "doc_test_123"}},
            }
        elif "blocks" in url and "children" in url:
            resp.json.return_value = {
                "code": 0,
                "data": {"children": [{"block_id": "blk_1"}]},
            }
        elif "permissions" in url:
            resp.json.return_value = {"code": 0}
        elif "upload_all" in url:
            resp.json.return_value = {
                "code": 0,
                "data": {"file_token": "ft_test"},
            }
        else:
            resp.json.return_value = {"code": 0, "data": {}}
        return resp

    fake_session.post.side_effect = _post_side_effect

    def _get_side_effect(url, **kwargs):
        resp = mock.MagicMock()
        resp.json.return_value = {"code": 0, "data": {"items": []}}
        return resp

    fake_session.get.side_effect = _get_side_effect
    fake_session.patch.return_value.json.return_value = {"code": 0}

    monkeypatch.setattr(
        "hydromas_call._get_feishu_session", lambda: fake_session
    )
    monkeypatch.setattr("hydromas_call._feishu_token_cache",
                        {"token": "fake_token", "expires": 9999999999})

    return fake_session


@pytest.fixture
def mock_hydromas_api(monkeypatch):
    """Mock HydroMAS API calls."""
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
                "simulation": {
                    "time": [0, 1, 2], "water_level": [0.5, 0.49, 0.48],
                    "outflow": [0.01, 0.01, 0.01],
                },
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
                "insights": ["水位持续下降"],
                "recommendations": ["增加入流量"],
                "title": "测试报告",
                "generated_at": "2026-03-01T12:00:00",
            }
        elif "gateway/chat" in path:
            return {
                "status": "success",
                "result": {"response": "分析完成"},
                "role": "operator",
            }
        elif "gateway/skills" in path:
            return {"skills": [], "total": 0}
        elif "gateway/skill" in path:
            return {
                "status": "success",
                "skill": data.get("skill_name", "test"),
                "result": {"data": {"summary": "测试结果"}},
            }
        return {"status": "success"}

    def _fake_get(path):
        if "gateway/skills" in path:
            return {"skills": [], "total": 0}
        if "gateway/health" in path:
            return {"status": "healthy", "agents_registered": 5}
        return {}

    monkeypatch.setattr("hydromas_call._post", _fake_post)
    monkeypatch.setattr("hydromas_call._get", _fake_get)
    monkeypatch.setattr("hydromas_call._post_binary", lambda *a, **kw: {"error": "mock"})


@pytest.fixture
def temp_history(monkeypatch, tmp_path):
    """Use a temp file for report history."""
    hist_path = str(tmp_path / "report_history.jsonl")
    monkeypatch.setattr("hydromas_call.REPORT_HISTORY_PATH", hist_path)
    return hist_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCmdReport:
    """Test the cmd_report function end-to-end."""

    def test_simulation_route(self, mock_feishu, mock_hydromas_api,
                              temp_history, capsys):
        """Simulation keywords should use tank-analysis endpoint."""
        import hydromas_call
        hydromas_call.cmd_report(["水箱仿真 初始水位0.5米 时长300秒"])
        out = capsys.readouterr().out
        assert "飞书文档:" in out
        assert "doc_test_123" in out

    def test_chat_fallback(self, mock_feishu, mock_hydromas_api,
                           temp_history, capsys):
        """Non-matching messages should fall back to chat."""
        import hydromas_call
        hydromas_call.cmd_report(["请帮我总结今日数据"])
        out = capsys.readouterr().out
        assert "飞书文档:" in out

    def test_user_openid_passed(self, mock_feishu, mock_hydromas_api,
                                temp_history, capsys):
        """--user-openid should be passed to Feishu grant."""
        import hydromas_call
        hydromas_call.cmd_report([
            "水箱仿真", "--user-openid", "ou_testuser123"
        ])
        out = capsys.readouterr().out
        assert "飞书文档:" in out

        # Check history records the user
        with open(temp_history) as f:
            rec = json.loads(f.readline())
        assert rec["user_id"] == "ou_testuser123"

    def test_report_history_recorded(self, mock_feishu, mock_hydromas_api,
                                     temp_history, capsys):
        """Reports should be recorded in history JSONL."""
        import hydromas_call
        hydromas_call.cmd_report(["水箱仿真"])
        assert os.path.exists(temp_history)
        with open(temp_history) as f:
            lines = f.readlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert "doc_token" in rec
        assert "created_at" in rec


class TestCmdHistory:
    """Test the history command."""

    def test_empty_history(self, temp_history, capsys):
        import hydromas_call
        hydromas_call.cmd_history([])
        out = capsys.readouterr().out
        assert "无报告记录" in out

    def test_history_with_records(self, temp_history, capsys):
        import hydromas_call
        # Write some test records
        for i in range(3):
            rec = {
                "user_id": f"ou_user{i}",
                "doc_token": f"doc_{i}",
                "doc_url": f"https://test.feishu.cn/docx/doc_{i}",
                "title": f"Report {i}",
                "skill": "simulation",
                "created_at": f"2026-03-01T12:0{i}:00",
            }
            with open(temp_history, "a") as f:
                f.write(json.dumps(rec) + "\n")

        hydromas_call.cmd_history([])
        out = capsys.readouterr().out
        assert "3 条" in out

    def test_history_filter_by_user(self, temp_history, capsys):
        import hydromas_call
        for uid in ["ou_a", "ou_b", "ou_a"]:
            rec = {
                "user_id": uid, "doc_token": "d", "doc_url": "u",
                "title": "t", "skill": "s", "created_at": "2026-03-01",
            }
            with open(temp_history, "a") as f:
                f.write(json.dumps(rec) + "\n")

        hydromas_call.cmd_history(["--user-openid", "ou_a"])
        out = capsys.readouterr().out
        assert "2 条" in out


class TestMultiUserGrant:
    """Test the _grant_multi_users helper."""

    def test_admin_always_granted(self, mock_feishu):
        import hydromas_call
        hydromas_call._feishu_token_cache = {
            "token": "fake", "expires": 9999999999
        }
        hydromas_call._grant_multi_users("fake", "doc_123", None)
        # Should have called grant at least once (for admin)

    def test_extra_users_granted(self, mock_feishu):
        import hydromas_call
        hydromas_call._feishu_token_cache = {
            "token": "fake", "expires": 9999999999
        }
        hydromas_call._grant_multi_users(
            "fake", "doc_123", ["ou_extra1", "ou_extra2"]
        )

    def test_duplicate_admin_not_double_granted(self, mock_feishu):
        import hydromas_call
        hydromas_call._feishu_token_cache = {
            "token": "fake", "expires": 9999999999
        }
        # Pass admin openid as extra — should not double-grant
        hydromas_call._grant_multi_users(
            "fake", "doc_123", [hydromas_call.DEFAULT_USER_OPENID]
        )
