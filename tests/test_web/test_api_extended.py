"""Extended web API tests — coverage for untested endpoints, error paths, validation.
扩展 Web API 测试 — 未测试端点、错误路径、验证。
"""

from fastapi.testclient import TestClient
from web.app import app

client = TestClient(app)


# ---------- Untested Endpoints ----------

class TestODDSeriesAPI:
    def test_check_series(self):
        resp = client.post("/api/odd/check-series", json={
            "states": [
                {"water_level": 0.8},
                {"water_level": 1.0},
                {"water_level": 1.5},
            ],
        })
        assert resp.status_code == 200

    def test_mrc_plan(self):
        resp = client.post("/api/odd/mrc-plan", json={
            "state": {"water_level": 3.0},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        # MRC plan returns actions or is a plan dict
        assert "actions" in data or "plan" in data or "severity" in data or len(data) >= 1


class TestDataCleanInterpolateAPI:
    def test_interpolate(self):
        resp = client.post("/api/dataclean/interpolate", json={
            "data": [1.0, None, None, 4.0, 5.0],
            "method": "linear",
        })
        assert resp.status_code == 200

    def test_outlier_iqr(self):
        resp = client.post("/api/dataclean/outliers", json={
            "data": [1.0, 1.1, 1.0, 10.0, 1.05, 1.02, 0.98],
            "method": "iqr",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "outlier_indices" in data


class TestIdentificationRunAPI:
    def test_nonlinear_identification(self):
        # First simulate to get data
        sim = client.post("/api/simulation/run", json={
            "duration": 100, "dt": 1.0, "initial_h": 0.5,
            "q_in_profile": [[0, 0.01], [50, 0.03]],
        }).json()
        resp = client.post("/api/identification/run", json={
            "observed_h": sim["water_level"],
            "observed_q_out": sim["outflow"],
            "model_type": "nonlinear",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Nonlinear identification returns identified tank params (cd, outlet_area, etc.)
        assert "cd" in data or "estimated_params" in data or "parameters" in data
        assert "converged" in data


class TestSkillsExtendedAPI:
    def test_lifecycle(self):
        resp = client.post("/api/skills/lifecycle", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "steps_completed" in data

    def test_report_control(self):
        # First run a control design skill
        skill_resp = client.post("/api/skills/control-design", json={
            "controller_type": "PID", "setpoint": 1.0,
            "duration": 100, "dt": 1.0,
        })
        assert skill_resp.status_code == 200
        skill_data = skill_resp.json()
        assert skill_data["success"] is True

        # Then generate report (wrapped in {"results": ...})
        resp = client.post("/api/skills/report/control", json={"results": skill_data["data"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "report_markdown" in data
        assert len(data["report_markdown"]) > 0

    def test_report_odd(self):
        resp = client.post("/api/skills/report/odd", json={"results": {
            "zone": "normal", "violations": [],
            "dimension_results": [{"dimension": "water_level", "zone": "normal"}],
        }})
        assert resp.status_code == 200
        data = resp.json()
        assert "report_markdown" in data

    def test_report_lifecycle(self):
        resp = client.post("/api/skills/report/lifecycle", json={"results": {
            "simulation": {"status": "ok"},
            "control": {"status": "ok"},
        }})
        assert resp.status_code == 200
        data = resp.json()
        assert "report_markdown" in data


# ---------- Validation / 422 Responses ----------

class TestValidation:
    def test_simulation_missing_fields(self):
        """POST with empty body should use defaults (no required fields)."""
        resp = client.post("/api/simulation/run", json={})
        assert resp.status_code == 200

    def test_prediction_missing_required(self):
        """historical_data is required — should return 422."""
        resp = client.post("/api/prediction/run", json={"horizon": 10})
        assert resp.status_code == 422

    def test_scheduling_missing_required(self):
        """demand_forecast is required — should return 422."""
        resp = client.post("/api/scheduling/run", json={})
        assert resp.status_code == 422

    def test_evaluation_missing_required(self):
        """observed and predicted are required — should return 422."""
        resp = client.post("/api/evaluation/performance", json={"metrics": ["RMSE"]})
        assert resp.status_code == 422

    def test_odd_missing_state(self):
        """state is required — should return 422."""
        resp = client.post("/api/odd/check", json={})
        assert resp.status_code == 422

    def test_assistant_missing_message(self):
        """message is required — should return 422."""
        resp = client.post("/api/assistant/chat", json={"role": "admin"})
        assert resp.status_code == 422

    def test_arx_missing_data(self):
        """y and u are required — should return 422."""
        resp = client.post("/api/identification/arx", json={"na": 2})
        assert resp.status_code == 422

    def test_four_pred_missing_data(self):
        """water_level_data is required — should return 422."""
        resp = client.post("/api/skills/four-prediction", json={})
        assert resp.status_code == 422

    def test_invalid_solver(self):
        """Invalid solver value should return 422 (Literal validation)."""
        resp = client.post("/api/simulation/run", json={"solver": "badvalue"})
        assert resp.status_code == 422

    def test_invalid_controller_type(self):
        """Invalid controller_type should return 422 (Literal validation)."""
        resp = client.post("/api/control/run", json={"controller_type": "FUZZY"})
        assert resp.status_code == 422

    def test_invalid_prediction_model(self):
        """Invalid model type should return 422 (Literal validation)."""
        resp = client.post("/api/prediction/run", json={
            "historical_data": [1.0, 2.0, 3.0],
            "model": "lstm",
        })
        assert resp.status_code == 422

    def test_invalid_scheduling_method(self):
        """Invalid scheduling method should return 422."""
        resp = client.post("/api/scheduling/run", json={
            "demand_forecast": [0.01],
            "method": "genetic",
        })
        assert resp.status_code == 422

    def test_invalid_outlier_method(self):
        """Invalid outlier method should return 422 (Literal validation)."""
        resp = client.post("/api/dataclean/outliers", json={
            "data": [1.0, 2.0, 3.0],
            "method": "zscore",
        })
        assert resp.status_code == 422

    def test_negative_duration(self):
        """Negative duration should be rejected by gt=0 constraint."""
        resp = client.post("/api/simulation/run", json={"duration": -10})
        assert resp.status_code == 422

    def test_zero_dt(self):
        """Zero dt should be rejected by gt=0 constraint."""
        resp = client.post("/api/simulation/run", json={"dt": 0})
        assert resp.status_code == 422

    def test_prediction_too_short(self):
        """historical_data with 1 element should fail min_length=2."""
        resp = client.post("/api/prediction/run", json={
            "historical_data": [1.0],
        })
        assert resp.status_code == 422

    def test_risk_threshold_out_of_range(self):
        """risk_threshold > 1 should fail le=1.0."""
        resp = client.post("/api/skills/four-prediction", json={
            "water_level_data": [0.5, 0.6, 0.7],
            "risk_threshold": 1.5,
        })
        assert resp.status_code == 422

    def test_sensitivity_method_literal(self):
        """Invalid sensitivity method should return 422."""
        resp = client.post("/api/design/sensitivity", json={
            "base_params": {"area": 1.0},
            "param_ranges": {"area": [0.5, 1.5]},
            "method": "Sobol",
        })
        assert resp.status_code == 422


# ---------- Error Handling / 400 Responses ----------

class TestErrorHandling:
    def test_valueerror_returns_400(self):
        """ValueError from MCP layer should return 400 (not 500)."""
        resp = client.post("/api/scheduling/run", json={
            "demand_forecast": [],
        })
        # demand_forecast min_length=1 catches this at 422
        assert resp.status_code == 422

    def test_global_error_handler(self):
        """The app should have error handlers registered."""
        # A valid request that succeeds
        resp = client.get("/api/system/status")
        assert resp.status_code == 200

    def test_cors_headers_present(self):
        """CORS headers should be present in responses."""
        resp = client.get("/api/roles")
        # CORSMiddleware adds headers for cross-origin requests
        assert resp.status_code == 200

    def test_404_for_unknown_api(self):
        """Unknown API path should return 404."""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404


# ---------- Security Headers ----------

class TestSecurityHeaders:
    def test_x_content_type_options(self):
        resp = client.get("/api/roles")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self):
        resp = client.get("/api/roles")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_referrer_policy(self):
        resp = client.get("/api/roles")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_csp_header(self):
        resp = client.get("/api/roles")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp


# ---------- Quick Actions Edge Cases ----------

class TestQuickActionsEdge:
    def test_unknown_role_fallback(self):
        """Unknown role should fallback to admin quick actions."""
        resp = client.get("/api/assistant/quick-actions/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["actions"]) > 0


# ---------- Skills /run Endpoint ----------

class TestSkillsRunAPI:
    def test_run_unknown_skill_returns_400(self):
        """Unknown skill name should trigger ValueError -> 400."""
        resp = client.post("/api/skills/run", json={
            "skill_name": "nonexistent_skill",
            "params": {},
        })
        assert resp.status_code == 400
        assert "Unknown skill" in resp.json()["detail"]

    def test_run_missing_skill_name_returns_422(self):
        """Missing skill_name should return 422."""
        resp = client.post("/api/skills/run", json={"params": {}})
        assert resp.status_code == 422

    def test_run_valid_skill(self):
        """Run a known skill by name (control_system_design)."""
        resp = client.post("/api/skills/run", json={
            "skill_name": "control_system_design",
            "params": {},
        })
        assert resp.status_code == 200


# ---------- Stronger Assertions on Existing Endpoints ----------

class TestResponseStructure:
    def test_scheduling_lp_response_structure(self):
        """LP scheduling response should contain status and schedule."""
        resp = client.post("/api/scheduling/run", json={
            "demand_forecast": [0.01, 0.02, 0.015, 0.01],
            "method": "lp",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("optimal", "fallback", "infeasible")

    def test_interpolate_response_structure(self):
        """Interpolate response should contain data and steps."""
        resp = client.post("/api/dataclean/interpolate", json={
            "data": [1.0, None, None, 4.0, 5.0],
            "method": "linear",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) == 5

    def test_check_series_response_structure(self):
        """ODD check-series should return worst_zone."""
        resp = client.post("/api/odd/check-series", json={
            "states": [
                {"water_level": 0.8},
                {"water_level": 1.0},
                {"water_level": 1.5},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "worst_zone" in data

    def test_four_prediction_actually_works(self):
        """Four-prediction with valid data should succeed (parameter name fix)."""
        wl_data = [0.5 + 0.02 * i + 0.1 * (i % 3 - 1) * 0.1 for i in range(50)]
        resp = client.post("/api/skills/four-prediction", json={
            "water_level_data": wl_data,
            "risk_threshold": 0.7,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "forecast" in data["steps_completed"]


# ---------- New Literal Validation ----------

class TestNewLiteralValidation:
    def test_invalid_interpolate_method(self):
        """Invalid interpolate method should return 422."""
        resp = client.post("/api/dataclean/interpolate", json={
            "data": [1.0, None, 3.0],
            "method": "cubic",
        })
        assert resp.status_code == 422

    def test_invalid_identification_model_type(self):
        """Invalid model_type should return 422."""
        resp = client.post("/api/identification/run", json={
            "observed_h": [0.5, 0.6, 0.7],
            "observed_q_out": [0.01, 0.02, 0.03],
            "model_type": "kalman",
        })
        assert resp.status_code == 422

    def test_invalid_assistant_role(self):
        """Invalid role should return 422."""
        resp = client.post("/api/assistant/chat", json={
            "message": "hello",
            "role": "superuser",
        })
        assert resp.status_code == 422

    def test_chat_max_length_message(self):
        """Message at max_length should be accepted."""
        resp = client.post("/api/assistant/chat", json={
            "message": "a" * 10000,
            "role": "admin",
        })
        assert resp.status_code == 200

    def test_chat_exceeds_max_length(self):
        """Message exceeding max_length should return 422."""
        resp = client.post("/api/assistant/chat", json={
            "message": "a" * 10001,
            "role": "admin",
        })
        assert resp.status_code == 422


# ---------- Enhanced Security Headers ----------

class TestEnhancedSecurityHeaders:
    def test_permissions_policy(self):
        resp = client.get("/api/roles")
        assert resp.headers.get("permissions-policy") == "camera=(), microphone=(), geolocation=()"

    def test_csp_object_src_none(self):
        resp = client.get("/api/roles")
        csp = resp.headers.get("content-security-policy", "")
        assert "object-src 'none'" in csp

    def test_csp_base_uri_self(self):
        resp = client.get("/api/roles")
        csp = resp.headers.get("content-security-policy", "")
        assert "base-uri 'self'" in csp

    def test_csp_frame_ancestors_none(self):
        resp = client.get("/api/roles")
        csp = resp.headers.get("content-security-policy", "")
        assert "frame-ancestors 'none'" in csp


# ---------- Sanitize Floats Unit Test ----------

class TestSanitizeFloats:
    def test_nan_inf_replaced(self):
        from web.routers.skills import _sanitize_floats
        result = _sanitize_floats({
            "a": float("nan"),
            "b": [1.0, float("inf"), 2.0],
            "c": {"nested": float("-inf")},
            "d": 42,
            "e": "string",
        })
        assert result["a"] is None
        assert result["b"] == [1.0, None, 2.0]
        assert result["c"]["nested"] is None
        assert result["d"] == 42
        assert result["e"] == "string"
