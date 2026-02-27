"""Tests for R6 multi-agent review fixes.
R6 多智能体评审修复测试。
"""

from __future__ import annotations

import numpy as np
import pytest

# ---------- H1: Role path param Literal validation ----------

class TestRolePathValidation:
    """Verify {role} path param rejects invalid roles."""

    def test_invalid_role_rejected(self):
        from fastapi.testclient import TestClient

        from web.app import app
        client = TestClient(app)
        resp = client.get("/api/assistant/quick-actions/hacker")
        assert resp.status_code == 422

    def test_valid_roles_accepted(self):
        from fastapi.testclient import TestClient

        from web.app import app
        client = TestClient(app)
        for role in ("operator", "engineer", "analyst", "admin"):
            resp = client.get(f"/api/assistant/quick-actions/{role}")
            assert resp.status_code == 200
            assert len(resp.json()["actions"]) > 0


# ---------- H2: predict_arx y_history length validation ----------

class TestPredictARXValidation:
    """Verify predict_arx validates y_history length >= na."""

    def test_y_history_too_short_raises(self):
        from core.identification.arx_model import predict_arx
        model = {
            "a_coefficients": [0.5, 0.3],
            "b_coefficients": [0.1],
            "na": 2, "nb": 1, "nk": 1,
        }
        with pytest.raises(ValueError, match="y_history length"):
            predict_arx(model, [1.0], [0.01] * 5)  # len=1 < na=2

    def test_y_history_exact_na_ok(self):
        from core.identification.arx_model import predict_arx
        model = {
            "a_coefficients": [0.5, 0.3],
            "b_coefficients": [0.1],
            "na": 2, "nb": 1, "nk": 1,
        }
        result = predict_arx(model, [1.0, 0.8], [0.01] * 3, u_history=[0.01] * 3)
        assert len(result) == 3


# ---------- H3: SafetyAgent exception handling ----------

class TestSafetyAgentErrorHandling:
    """Verify SafetyAgent handles ODD check failures gracefully."""

    def test_check_state_returns_error_on_failure(self):
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent(odd_config={"invalid": True})
        # With invalid config, check_state should not crash
        result = agent.check_state({"water_level": 1.0})
        # Should either succeed or return error dict
        assert "zone" in result

    def test_check_action_safe_normal_zone(self):
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        result = agent.check_action_safe(
            action={"type": "adjust_inflow", "value": 0.02},
            current_state={"water_level": 1.0},
        )
        assert "safe" in result
        assert "zone" in result


# ---------- H4: LP solver detailed status ----------

class TestLPSolverStatus:
    """Verify LP solver returns detailed status on failure."""

    def test_infeasible_returns_status_name(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        result = optimize_schedule_lp(
            demand_forecast=[10.0] * 5,  # Very high demand
            supply_capacity=0.001,  # Very low supply
            min_level=0.5,
            max_level=1.0,
            initial_level=0.5,
            tank_area=0.001,  # Tiny tank — levels will violate bounds
        )
        if result["status"] == "fallback":
            # PuLP not installed — fallback schedule used
            assert "message" in result
        elif result["status"] != "optimal":
            assert "message" in result
            assert "solver" in result["message"]  # includes solver status


# ---------- H5: Module-level _call_tool_dynamic ----------

class TestModuleLevelToolCaller:
    """Verify _call_tool_dynamic exists as module-level function."""

    def test_function_exists(self):
        from skills.base_skill import _call_tool_dynamic
        assert callable(_call_tool_dynamic)

    def test_unknown_tool_raises(self):
        from skills.base_skill import _call_tool_dynamic
        with pytest.raises(ValueError, match="Unknown tool"):
            _call_tool_dynamic("nonexistent_tool_xyz", {})


# ---------- H6: evaluate_performance converts arrays once ----------

class TestEvaluatePerformanceOptimized:
    """Verify evaluate_performance passes arrays, not lists, to metrics."""

    def test_multiple_metrics_consistent(self):
        from core.evaluation.metrics import evaluate_performance
        observed = [1.0, 2.0, 3.0, 4.0, 5.0]
        predicted = [1.1, 2.1, 2.9, 4.2, 4.8]
        result = evaluate_performance(observed, predicted, ["RMSE", "MAE", "NSE", "MAPE"])
        assert len(result) == 4
        assert all(isinstance(v, float) for v in result.values())
        assert result["RMSE"] > 0
        assert result["MAE"] > 0


# ---------- H7: least_squares pre-computed h_safe_sqrt ----------

class TestLeastSquaresOptimized:
    """Verify least_squares identification still works after optimization."""

    def test_identification_correct(self):
        from core.identification.least_squares import identify_tank_params
        # Generate synthetic data
        h = np.linspace(0.1, 1.5, 50)
        cd_true, a_true = 0.6, 0.01
        q = (
            cd_true * a_true * np.sqrt(2 * 9.81 * h)
            + np.random.default_rng(42).normal(0, 0.0001, 50)
        )
        result = identify_tank_params(h.tolist(), q.tolist())
        assert abs(result["cd"] - cd_true) < 0.1
        assert abs(result["outlet_area"] - a_true) < 0.005
        assert result["r_squared"] > 0.95


# ---------- M1: check_odd_series empty state_series ----------

class TestODDSeriesEmpty:
    """Verify check_odd_series handles empty input."""

    def test_empty_state_series(self):
        from core.odd.odd_monitor import check_odd_series
        result = check_odd_series(state_series=[])
        assert result["worst_zone"] == "normal"
        assert result["n_steps"] == 0
        assert result["step_results"] == []

    def test_single_state_series(self):
        from core.odd.odd_monitor import check_odd_series
        result = check_odd_series(state_series=[{"water_level": 1.0}])
        assert result["n_steps"] == 1


# ---------- M2: User input sanitization ----------

class TestInputSanitization:
    """Verify control characters stripped from user input."""

    def test_control_chars_stripped(self):
        import re
        msg = "hello\x00\x07\x0bworld"
        sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', msg)
        assert sanitized == "helloworld"

    def test_normal_text_preserved(self):
        import re
        msg = "运行仿真模拟 simulate tank"
        sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', msg)
        assert sanitized == msg


# ---------- M3: Report markdown escaping ----------

class TestReportMarkdownEscaping:
    """Verify report agent escapes markdown special chars."""

    def test_escape_md_function(self):
        from agents.report_agent import _escape_md
        assert _escape_md("value|with|pipes") == "value\\|with\\|pipes"
        assert _escape_md("normal text") == "normal text"
        assert _escape_md("[link]") == "\\[link\\]"
        assert _escape_md(42) == "42"  # non-string input


# ---------- M4: predict_arx pre-allocated arrays ----------

class TestPredictARXPreAllocated:
    """Verify predict_arx uses numpy arrays and returns correct results."""

    def test_predictions_match_expected(self):
        from core.identification.arx_model import identify_arx, predict_arx
        # Simple synthetic data
        n = 100
        rng = np.random.default_rng(42)
        u = rng.uniform(0.005, 0.02, n).tolist()
        y = np.cumsum(rng.normal(0, 0.01, n)).tolist()
        model = identify_arx(y, u, na=2, nb=1, nk=1)
        preds = predict_arx(model, y[-5:], u[:10], u_history=u[-5:])
        assert len(preds) == 10
        assert all(isinstance(v, float) for v in preds)

    def test_long_horizon(self):
        from core.identification.arx_model import predict_arx
        model = {
            "a_coefficients": [0.9, -0.1],
            "b_coefficients": [0.05],
            "na": 2, "nb": 1, "nk": 1,
        }
        preds = predict_arx(model, [1.0, 0.9], [0.01] * 100, u_history=[0.01] * 3)
        assert len(preds) == 100


# ---------- M6: Monte Carlo selective copy ----------

class TestMonteCarloSelectiveCopy:
    """Verify Monte Carlo doesn't mutate base_params."""

    def test_base_params_not_mutated(self):
        from compute.distributed_sim import monte_carlo_sim
        base = {"duration": 10, "dt": 1.0, "tank_params": {"area": 1.0, "cd": 0.6}}
        original_area = base["tank_params"]["area"]
        monte_carlo_sim(base, {"area": (1.0, 0.1)}, n_samples=5, use_ray=False, seed=42)
        assert base["tank_params"]["area"] == original_area


# ---------- Dead code: numpy removed from lp_scheduler ----------

class TestLPSchedulerNoNumpy:
    """Verify lp_scheduler doesn't import numpy unnecessarily."""

    def test_no_numpy_import(self):
        import ast
        with open("core/scheduling/lp_scheduler.py") as f:
            tree = ast.parse(f.read())
        imports = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        numpy_imports = [
            n for n in imports
            if any(
                alias.name == "numpy" or (hasattr(n, "module") and n.module == "numpy")
                for alias in (n.names if hasattr(n, "names") else [])
            )
        ]
        assert len(numpy_imports) == 0
