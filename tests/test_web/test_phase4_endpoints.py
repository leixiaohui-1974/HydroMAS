"""Tests for Phase 4 orchestration endpoints — lifecycle, skill management, dashboard.
Phase 4 编排端点测试 — 生命周期、技能管理、仪表板。

Tests cover:
- POST /api/orchestration/agents/{id}/lifecycle (start/stop/pause/resume)
- POST /api/orchestration/agents/batch-lifecycle (batch operations)
- POST /api/orchestration/cross-domain-workflow (NL workflow)
- GET  /api/orchestration/skills (list all skills)
- GET  /api/orchestration/skills/{name} (skill detail)
- POST /api/orchestration/skills/{name}/execute (execute skill)
- GET  /api/orchestration/dashboard (aggregated dashboard)
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


# ---------- Agent Lifecycle ----------

class TestAgentLifecycle:
    """Test POST /api/orchestration/agents/{agent_id}/lifecycle."""

    def test_pause_agent(self, client):
        resp = client.post(
            "/api/orchestration/agents/planning/lifecycle",
            json={"action": "pause"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "planning"
        assert data["action"] == "pause"
        assert data["current_status"] == "paused"

    def test_resume_paused_agent(self, client):
        # First pause
        client.post(
            "/api/orchestration/agents/planning/lifecycle",
            json={"action": "pause"},
        )
        # Then resume
        resp = client.post(
            "/api/orchestration/agents/planning/lifecycle",
            json={"action": "resume"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_status"] == "idle"

    def test_resume_non_paused_agent_error(self, client):
        # Ensure agent is idle first
        client.post(
            "/api/orchestration/agents/analysis/lifecycle",
            json={"action": "start"},
        )
        resp = client.post(
            "/api/orchestration/agents/analysis/lifecycle",
            json={"action": "resume"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_start_agent(self, client):
        resp = client.post(
            "/api/orchestration/agents/report/lifecycle",
            json={"action": "start"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "report"
        assert data["current_status"] == "idle"

    def test_stop_agent(self, client):
        resp = client.post(
            "/api/orchestration/agents/report/lifecycle",
            json={"action": "stop"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "report"

    def test_lifecycle_nonexistent_agent(self, client):
        resp = client.post(
            "/api/orchestration/agents/nonexistent/lifecycle",
            json={"action": "start"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_lifecycle_invalid_action(self, client):
        resp = client.post(
            "/api/orchestration/agents/planning/lifecycle",
            json={"action": "invalid"},
        )
        assert resp.status_code == 422  # Pydantic validation error


class TestBatchLifecycle:
    """Test POST /api/orchestration/agents/batch-lifecycle."""

    def test_batch_pause(self, client):
        resp = client.post(
            "/api/orchestration/agents/batch-lifecycle",
            json={
                "action": "pause",
                "agent_ids": ["planning", "analysis"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "pause"
        assert len(data["results"]) == 2
        assert all(r["current_status"] == "paused" for r in data["results"])

    def test_batch_with_nonexistent(self, client):
        resp = client.post(
            "/api/orchestration/agents/batch-lifecycle",
            json={
                "action": "start",
                "agent_ids": ["planning", "nonexistent"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2
        # One should succeed, one should have error
        errors = [r for r in data["results"] if "error" in r]
        assert len(errors) == 1
        assert errors[0]["agent_id"] == "nonexistent"

    def test_batch_start_multiple(self, client):
        resp = client.post(
            "/api/orchestration/agents/batch-lifecycle",
            json={
                "action": "start",
                "agent_ids": ["planning", "analysis", "report"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 3


# ---------- Cross-Domain Workflow ----------

class TestCrossDomainWorkflow:
    """Test POST /api/orchestration/cross-domain-workflow."""

    def test_cross_domain_workflow(self, client):
        resp = client.post(
            "/api/orchestration/cross-domain-workflow",
            json={
                "user_input": "分析当前水位数据并生成预警报告",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should return workflow execution result
        assert isinstance(data, dict)

    def test_cross_domain_with_params(self, client):
        resp = client.post(
            "/api/orchestration/cross-domain-workflow",
            json={
                "user_input": "预测未来水位变化趋势",
                "params": {"horizon": 24},
            },
        )
        assert resp.status_code == 200


# ---------- Skill Management ----------

class TestSkillList:
    """Test GET /api/orchestration/skills."""

    def test_list_skills(self, client):
        resp = client.get("/api/orchestration/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_skills" in data
        assert "skills" in data
        assert data["total_skills"] >= 15
        assert len(data["skills"]) == data["total_skills"]

    def test_skills_have_metadata(self, client):
        resp = client.get("/api/orchestration/skills")
        data = resp.json()
        for skill in data["skills"]:
            assert "name" in skill
            assert "has_instance" in skill

    def test_forecast_skill_in_list(self, client):
        resp = client.get("/api/orchestration/skills")
        data = resp.json()
        names = [s["name"] for s in data["skills"]]
        assert "forecast_skill" in names


class TestSkillDetail:
    """Test GET /api/orchestration/skills/{skill_name}."""

    def test_get_forecast_skill(self, client):
        resp = client.get("/api/orchestration/skills/forecast_skill")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "forecast_skill"
        assert data["has_instance"] is True
        assert "trigger_phrases" in data
        assert "input_schema" in data
        assert "tools_required" in data
        assert "predict_future" in data["tools_required"]

    def test_get_leak_diagnosis_skill(self, client):
        resp = client.get("/api/orchestration/skills/leak_diagnosis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "leak_diagnosis"
        assert "display_name" in data

    def test_get_nonexistent_skill(self, client):
        resp = client.get("/api/orchestration/skills/nonexistent_skill")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


class TestSkillExecution:
    """Test POST /api/orchestration/skills/{name}/execute."""

    def test_execute_nonexistent_skill(self, client):
        resp = client.post(
            "/api/orchestration/skills/nonexistent/execute",
            json={"skill_name": "nonexistent", "params": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_execute_skill_returns_result(self, client):
        # Execute forecast skill — will likely fail on missing data
        # but should return a structured result, not a crash
        resp = client.post(
            "/api/orchestration/skills/forecast_skill/execute",
            json={
                "skill_name": "forecast_skill",
                "params": {
                    "historical_data": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5],
                    "horizon": 3,
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "skill" in data
        assert data["skill"] == "forecast_skill"
        assert "success" in data
        assert "execution_time" in data


# ---------- Dashboard ----------

class TestDashboard:
    """Test GET /api/orchestration/dashboard."""

    def test_dashboard_returns_all_sections(self, client):
        resp = client.get("/api/orchestration/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert "health" in data
        assert "skills" in data
        assert "execution" in data
        assert "messages" in data

    def test_dashboard_agents_section(self, client):
        resp = client.get("/api/orchestration/dashboard")
        data = resp.json()
        agents = data["agents"]
        assert agents["total"] == 15
        assert "by_status" in agents
        assert agents["bus_connected"] is True

    def test_dashboard_skills_section(self, client):
        resp = client.get("/api/orchestration/dashboard")
        data = resp.json()
        skills = data["skills"]
        assert skills["total"] >= 15
        assert isinstance(skills["names"], list)
        assert "forecast_skill" in skills["names"]

    def test_dashboard_health_section(self, client):
        resp = client.get("/api/orchestration/dashboard")
        data = resp.json()
        health = data["health"]
        assert "total_requests" in health
        assert "total_errors" in health
        assert "error_rate" in health

    def test_dashboard_execution_section(self, client):
        resp = client.get("/api/orchestration/dashboard")
        data = resp.json()
        execution = data["execution"]
        assert "total_plans" in execution
        assert "recent_plans" in execution
