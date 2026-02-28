"""Tests for the orchestration API router — multi-agent management.
多智能体编排 API 路由测试。

Tests cover:
- GET /api/orchestration/agents (list all agents)
- GET /api/orchestration/agents/{agent_id} (agent details)
- GET /api/orchestration/agents/by-capability/{cap} (capability search)
- POST /api/orchestration/agents/{agent_id}/message (send message)
- POST /api/orchestration/execute-plan (DAG execution)
- GET /api/orchestration/message-history (bus history)
- GET /api/orchestration/architecture (platform overview)
- GET /api/orchestration/health (all agents health check)
- GET /api/orchestration/agents/{agent_id}/health (single agent health check)
- GET /api/orchestration/metrics (platform metrics)
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


class TestListAgents:
    """Test GET /api/orchestration/agents."""

    def test_list_agents_returns_all(self, client):
        resp = client.get("/api/orchestration/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_agents" in data
        assert data["total_agents"] == 15
        assert "agents" in data
        assert len(data["agents"]) == 15

    def test_list_agents_has_expected_ids(self, client):
        resp = client.get("/api/orchestration/agents")
        data = resp.json()
        agent_ids = {a["id"] for a in data["agents"]}
        expected = {
            "orchestrator", "planning", "analysis", "report",
            "safety", "handuo", "rl_dispatch",
            "dev_planner", "dev_reviewer", "dev_tester", "dev_orchestrator",
            "content_planner", "content_reviewer", "content_publisher",
            "content_orchestrator",
        }
        assert agent_ids == expected

    def test_agents_have_capabilities(self, client):
        resp = client.get("/api/orchestration/agents")
        data = resp.json()
        for agent_info in data["agents"]:
            assert "capabilities" in agent_info
            assert isinstance(agent_info["capabilities"], list)
            assert len(agent_info["capabilities"]) > 0


class TestGetAgent:
    """Test GET /api/orchestration/agents/{agent_id}."""

    def test_get_existing_agent(self, client):
        resp = client.get("/api/orchestration/agents/planning")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "planning"
        assert data["type"] == "PlanningAgent"
        assert "task_decomposition" in data["capabilities"]

    def test_get_content_agent(self, client):
        resp = client.get("/api/orchestration/agents/content_planner")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "content_planner"
        assert "requirement_analysis" in data["capabilities"]

    def test_get_nonexistent_agent(self, client):
        resp = client.get("/api/orchestration/agents/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


class TestFindByCapability:
    """Test GET /api/orchestration/agents/by-capability/{capability}."""

    def test_find_task_decomposition(self, client):
        resp = client.get("/api/orchestration/agents/by-capability/task_decomposition")
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "task_decomposition"
        assert len(data["agents"]) >= 1
        assert any(a["id"] == "planning" for a in data["agents"])

    def test_find_no_match(self, client):
        resp = client.get("/api/orchestration/agents/by-capability/nonexistent_capability")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 0

    def test_find_content_capability(self, client):
        resp = client.get("/api/orchestration/agents/by-capability/outline_generation")
        assert resp.status_code == 200
        data = resp.json()
        assert any(a["id"] == "content_planner" for a in data["agents"])


class TestSendMessage:
    """Test POST /api/orchestration/agents/{agent_id}/message."""

    def test_send_message_to_planner(self, client):
        resp = client.post(
            "/api/orchestration/agents/content_planner/message",
            json={"action": "plan", "params": {"text": "写一篇AI文章"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "response"
        assert "result" in data["content"]

    def test_send_message_to_reviewer(self, client):
        resp = client.post(
            "/api/orchestration/agents/content_reviewer/message",
            json={
                "action": "review_article",
                "params": {"content": "# Title\n\n## Intro\n\nContent.\n\n## End\n\nConclusion."},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "response"

    def test_send_message_to_nonexistent(self, client):
        resp = client.post(
            "/api/orchestration/agents/nonexistent/message",
            json={"action": "test", "params": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


class TestExecutePlan:
    """Test POST /api/orchestration/execute-plan."""

    def test_execute_sequential_plan(self, client):
        resp = client.post(
            "/api/orchestration/execute-plan",
            json={
                "objective": "Plan and review content",
                "tasks": [
                    {
                        "task_id": "t1",
                        "agent_id": "content_planner",
                        "action": "plan",
                        "params": {"text": "写一篇关于水网的文章"},
                        "dependencies": [],
                    },
                    {
                        "task_id": "t2",
                        "agent_id": "content_reviewer",
                        "action": "review_article",
                        "params": {"content": "# Test\n\n## Section\n\nContent."},
                        "dependencies": ["t1"],
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["objective"] == "Plan and review content"
        assert data["status"] == "completed"
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["status"] == "completed"
        assert data["tasks"][1]["status"] == "completed"

    def test_execute_plan_validation_error(self, client):
        # Circular dependency
        resp = client.post(
            "/api/orchestration/execute-plan",
            json={
                "objective": "Bad plan",
                "tasks": [
                    {
                        "task_id": "a",
                        "agent_id": "content_planner",
                        "action": "plan",
                        "params": {},
                        "dependencies": ["b"],
                    },
                    {
                        "task_id": "b",
                        "agent_id": "content_reviewer",
                        "action": "review_article",
                        "params": {},
                        "dependencies": ["a"],
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


class TestMessageHistory:
    """Test GET /api/orchestration/message-history."""

    def test_get_history(self, client):
        resp = client.get("/api/orchestration/message-history")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert "count" in data

    def test_get_history_with_limit(self, client):
        resp = client.get("/api/orchestration/message-history?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 5


class TestHealthEndpoints:
    """Test health check and metrics endpoints."""

    def test_check_all_health(self, client):
        resp = client.get("/api/orchestration/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "healthy" in data
        assert "unhealthy" in data
        assert "agents" in data
        assert data["total"] == 15

    def test_check_agent_health(self, client):
        resp = client.get("/api/orchestration/agents/planning/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "planning"
        assert "healthy" in data

    def test_check_nonexistent_agent_health(self, client):
        resp = client.get("/api/orchestration/agents/nonexistent/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is False

    def test_platform_metrics(self, client):
        resp = client.get("/api/orchestration/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_agents" in data
        assert "total_requests" in data
        assert "overall_error_rate" in data


class TestPlanManagement:
    """Test Phase 2 plan management endpoints."""

    def test_list_execution_plans(self, client):
        resp = client.get("/api/orchestration/execution-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "plans" in data
        assert "total" in data

    def test_get_agent_metrics(self, client):
        resp = client.get("/api/orchestration/agents/planning/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_id" in data or "request_count" in data

    def test_list_capabilities(self, client):
        resp = client.get("/api/orchestration/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_capabilities" in data
        assert "capabilities" in data
        assert data["total_capabilities"] > 0
        # task_decomposition should be in the capability map
        assert "task_decomposition" in data["capabilities"]


class TestArchitecture:
    """Test GET /api/orchestration/architecture."""

    def test_architecture_overview(self, client):
        resp = client.get("/api/orchestration/architecture")
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "HydroOS-Agent"
        assert "layers" in data
        assert data["layers"]["L4_agents"]["total"] == 15
        assert "capability_map" in data
        assert data["bus_connected"] is True

    def test_architecture_capability_map(self, client):
        resp = client.get("/api/orchestration/architecture")
        data = resp.json()
        cap_map = data["capability_map"]
        # Planning agent should show up for task_decomposition
        assert "task_decomposition" in cap_map
        assert "planning" in cap_map["task_decomposition"]
