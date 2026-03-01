"""Tests for web API endpoints.
Web API 接口测试。
"""

import pytest
from fastapi.testclient import TestClient

from web.app import app

client = TestClient(app)


# ---------- System / Roles ----------

class TestSystemEndpoints:
    def test_index_page(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "HydroOS-Agent" in resp.text

    def test_roles(self):
        resp = client.get("/api/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert "operator" in data
        assert "engineer" in data
        assert "analyst" in data
        assert "admin" in data

    def test_system_status(self):
        resp = client.get("/api/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert data["odd_dimensions"] == 6


# ---------- Simulation ----------

class TestSimulationAPI:
    def test_run_simulation(self):
        resp = client.post("/api/simulation/run", json={
            "duration": 50, "dt": 1.0, "initial_h": 0.5,
            "q_in_profile": [[0, 0.01]],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "water_level" in data
        assert "time" in data
        assert len(data["water_level"]) == len(data["time"])

    def test_simulation_defaults(self):
        resp = client.get("/api/simulation/defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert "tank_params" in data
        assert "simulation_params" in data

    def test_simulation_rk4(self):
        resp = client.post("/api/simulation/run", json={
            "duration": 50, "dt": 1.0, "initial_h": 0.5,
            "q_in_profile": [[0, 0.01]], "solver": "rk4",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["solver"].lower() == "rk4"


# ---------- Control ----------

class TestControlAPI:
    def test_run_pid(self):
        resp = client.post("/api/control/run", json={
            "setpoint": 1.0, "controller_type": "PID",
            "duration": 100, "initial_h": 0.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "water_level" in data
        assert "control_output" in data

    def test_run_mpc(self):
        resp = client.post("/api/control/run", json={
            "setpoint": 1.0, "controller_type": "MPC",
            "duration": 50, "initial_h": 0.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["solver"] == "Euler+MPC"

    def test_control_defaults(self):
        resp = client.get("/api/control/defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert "pid" in data
        assert "mpc" in data


# ---------- Prediction ----------

class TestPredictionAPI:
    def test_predict_linear(self):
        resp = client.post("/api/prediction/run", json={
            "historical_data": [0.5 + 0.01 * i for i in range(50)],
            "horizon": 10, "model": "linear",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["predictions"]) == 10

    def test_predict_polynomial(self):
        resp = client.post("/api/prediction/run", json={
            "historical_data": [0.5 + 0.01 * i for i in range(50)],
            "horizon": 10, "model": "polynomial", "degree": 3,
        })
        assert resp.status_code == 200

    def test_sample_data(self):
        resp = client.get("/api/prediction/sample-data")
        assert resp.status_code == 200
        data = resp.json()
        assert "water_level" in data


# ---------- Scheduling ----------

class TestSchedulingAPI:
    def test_scheduling_lp(self):
        resp = client.post("/api/scheduling/run", json={
            "demand_forecast": [0.01, 0.02, 0.015, 0.01],
            "method": "lp",
        })
        assert resp.status_code == 200

    def test_scheduling_rule(self):
        resp = client.post("/api/scheduling/run", json={
            "demand_forecast": [0.01, 0.02], "method": "rule",
        })
        assert resp.status_code == 200


# ---------- Evaluation ----------

class TestEvaluationAPI:
    def test_performance(self):
        resp = client.post("/api/evaluation/performance", json={
            "observed": [1.0] * 10,
            "predicted": [0.5, 0.8, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "metrics": ["RMSE", "MAE"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "RMSE" in data

    def test_wnal(self):
        resp = client.post("/api/evaluation/wnal", json={
            "capabilities": {
                "sensing": 80, "communication": 70, "modeling": 65,
                "prediction": 60, "control": 75, "odd_monitoring": 50,
                "decision_support": 40,
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "level" in data
        assert data["level"].startswith("L")


# ---------- ODD ----------

class TestODDAPI:
    def test_check_odd_normal(self):
        resp = client.post("/api/odd/check", json={
            "state": {"water_level": 1.0},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["zone"] == "normal"

    def test_check_odd_mrc(self):
        resp = client.post("/api/odd/check", json={
            "state": {"water_level": 3.0},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["zone"] == "mrc"

    def test_odd_specs(self):
        resp = client.get("/api/odd/specs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dimensions"]) == 6


# ---------- Design ----------

class TestDesignAPI:
    def test_sensitivity_oat(self):
        resp = client.post("/api/design/sensitivity", json={
            "base_params": {"area": 1.0, "cd": 0.6},
            "param_ranges": {"area": [0.5, 1.5], "cd": [0.3, 0.9]},
            "method": "OAT",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["method"] == "OAT"

    def test_sizing(self):
        resp = client.post("/api/design/sizing", json={
            "demand_peak": 0.03, "duration_hours": 4.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "optimal_area" in data or "required_volume" in data


# ---------- DataClean ----------

class TestDataCleanAPI:
    def test_detect_outliers(self):
        resp = client.post("/api/dataclean/outliers", json={
            "data": [1.0, 1.1, 1.0, 5.0, 1.05, 1.02],
            "method": "3sigma",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "outlier_indices" in data


# ---------- Identification ----------

class TestIdentificationAPI:
    def test_arx(self):
        import math
        y = [0.5 + 0.005 * i + 0.02 * math.sin(i / 3) for i in range(50)]
        u = [0.01 + 0.005 * math.sin(i / 5) for i in range(50)]
        resp = client.post("/api/identification/arx", json={
            "y": y, "u": u, "na": 2, "nb": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "r_squared" in data


# ---------- Skills ----------

class TestSkillsAPI:
    def test_list_skills(self):
        resp = client.get("/api/skills/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert len(data["skills"]) > 0

    @pytest.mark.asyncio
    async def test_four_prediction(self):
        resp = client.post("/api/skills/four-prediction", json={
            "water_level_data": [0.5 + 0.02 * i for i in range(50)],
            "risk_threshold": 0.7,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "steps_completed" in data

    def test_control_design(self):
        resp = client.post("/api/skills/control-design", json={
            "controller_type": "PID", "setpoint": 1.0,
            "duration": 100, "dt": 1.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ---------- Assistant ----------

class TestAssistantAPI:
    def test_chat_simulation(self):
        resp = client.post("/api/assistant/chat", json={
            "message": "运行仿真模拟",
            "role": "designer",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "intent" in data
        assert data["intent"]["route_type"] in ("skill", "tool", "agent")

    def test_chat_forecast(self):
        resp = client.post("/api/assistant/chat", json={
            "message": "预测未来水位",
            "role": "researcher",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "intent" in data

    def test_quick_actions(self):
        for role in ["operator", "engineer", "analyst", "admin"]:
            resp = client.get(f"/api/assistant/quick-actions/{role}")
            assert resp.status_code == 200
            data = resp.json()
            assert "actions" in data
            assert len(data["actions"]) > 0

    def test_capabilities(self):
        resp = client.get("/api/assistant/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "tool_keywords" in data
        assert "supported_roles" in data
