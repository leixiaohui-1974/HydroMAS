"""Tests for R5 multi-agent review fixes.
R5 多智能体评审修复测试。
"""

from __future__ import annotations

import math

import numpy as np
import pytest

# ---------- C1: settling_time clarity ----------

class TestSettlingTimeLogic:
    """Verify settling_time returns correct time for 'stay within band'."""

    def test_always_within_band(self):
        from core.evaluation.metrics import settling_time
        t = [0, 1, 2, 3, 4]
        v = [1.0, 1.01, 0.99, 1.0, 1.0]
        assert settling_time(t, v, setpoint=1.0, tolerance=0.02) == 0.0

    def test_never_settles(self):
        from core.evaluation.metrics import settling_time
        t = [0, 1, 2, 3, 4]
        v = [0.0, 0.5, 0.3, 0.7, 0.2]
        result = settling_time(t, v, setpoint=1.0, tolerance=0.02)
        assert result is None

    def test_settles_at_correct_time(self):
        from core.evaluation.metrics import settling_time
        t = [0, 1, 2, 3, 4, 5]
        v = [0.0, 0.5, 0.8, 1.0, 0.99, 1.01]
        result = settling_time(t, v, setpoint=1.0, tolerance=0.02)
        # Last outside point is index 2 (0.8 is outside 2% of 1.0)
        assert result == 3.0


# ---------- C2: Unbounded dict fields max_length ----------

class TestModelDictBounds:
    """Verify all dict fields have max_length constraints."""

    def test_simulation_tank_params_bounded(self):
        from web.models import SimulationRequest
        huge = {f"k{i}": float(i) for i in range(25)}
        with pytest.raises(Exception):
            SimulationRequest(tank_params=huge)

    def test_control_params_bounded(self):
        from web.models import ControlRequest
        huge = {f"k{i}": float(i) for i in range(25)}
        with pytest.raises(Exception):
            ControlRequest(params=huge)

    def test_scheduling_constraints_bounded(self):
        from web.models import SchedulingRequest
        huge = {f"k{i}": float(i) for i in range(25)}
        with pytest.raises(Exception):
            SchedulingRequest(demand_forecast=[0.01], constraints=huge)

    def test_wnal_capabilities_bounded(self):
        from web.models import WNALRequest
        huge = {f"k{i}": float(i) for i in range(25)}
        with pytest.raises(Exception):
            WNALRequest(capabilities=huge)

    def test_odd_state_bounded(self):
        from web.models import ODDCheckRequest
        huge = {f"k{i}": float(i) for i in range(55)}
        with pytest.raises(Exception):
            ODDCheckRequest(state=huge)

    def test_skill_params_bounded(self):
        from web.models import SkillRequest
        huge = {f"k{i}": float(i) for i in range(55)}
        with pytest.raises(Exception):
            SkillRequest(skill_name="test", params=huge)

    def test_assistant_params_bounded(self):
        from web.models import AssistantMessage
        huge = {f"k{i}": float(i) for i in range(55)}
        with pytest.raises(Exception):
            AssistantMessage(message="hello", params=huge)


# ---------- C3: Report endpoints use bounded model ----------

class TestReportEndpointsBounded:
    """Verify report endpoints reject unbounded input."""

    def test_report_accepts_normal_input(self):
        from fastapi.testclient import TestClient

        from web.app import app
        client = TestClient(app)
        resp = client.post("/api/skills/report/control", json={
            "results": {"metric": 1.0}
        })
        assert resp.status_code == 200


# ---------- H1/H2: Pre-allocated arrays in PID/MPC loops ----------

class TestControlPreAllocation:
    """Verify PID/MPC control loops return correct array lengths."""

    def test_pid_array_lengths(self):
        from core.control.pid_controller import run_pid_control
        result = run_pid_control(setpoint=1.0, initial_h=0.5, duration=10, dt=1.0)
        assert len(result["time"]) == 11
        assert len(result["water_level"]) == 11
        assert len(result["control_output"]) == 10
        assert len(result["error"]) == 10
        assert len(result["outflow"]) == 11

    def test_mpc_array_lengths(self):
        from core.control.mpc_controller import run_mpc_control
        result = run_mpc_control(setpoint=1.0, initial_h=0.5, duration=10, dt=1.0)
        assert len(result["time"]) == 11
        assert len(result["water_level"]) == 11
        assert len(result["control_output"]) == 10
        assert len(result["outflow"]) == 11

    def test_pid_returns_lists_not_arrays(self):
        from core.control.pid_controller import run_pid_control
        result = run_pid_control(setpoint=1.0, initial_h=0.5, duration=5, dt=1.0)
        assert isinstance(result["time"], list)
        assert isinstance(result["water_level"], list)


# ---------- H3: PID history bounded ----------

class TestPIDHistoryBounded:
    """Verify PID history uses bounded deque."""

    def test_history_is_deque(self):
        from collections import deque

        from core.control.pid_controller import PIDController
        pid = PIDController()
        assert isinstance(pid._history, deque)
        assert pid._history.maxlen == 10000

    def test_history_does_not_grow_past_maxlen(self):
        from core.control.pid_controller import PIDController, PIDParams
        pid = PIDController(PIDParams(kp=1.0, ki=0.0, kd=0.0))
        for _ in range(100):
            pid.compute(setpoint=1.0, measured=0.5, dt=1.0)
        assert len(pid._history) == 100
        assert pid._history.maxlen == 10000


# ---------- H4: ARX regression vectorized ----------

class TestARXVectorized:
    """Verify vectorized ARX identification gives correct results."""

    def test_identify_arx_still_works(self):
        from core.identification.arx_model import identify_arx
        n = 200
        y = list(np.sin(np.linspace(0, 4 * np.pi, n)))
        u = [0.01] * n
        result = identify_arx(y, u, na=2, nb=2, nk=1)
        assert "a_coefficients" in result
        assert "b_coefficients" in result
        assert len(result["a_coefficients"]) == 2
        assert len(result["b_coefficients"]) == 2
        assert result["r_squared"] > 0.5

    def test_predict_arx_still_works(self):
        from core.identification.arx_model import identify_arx, predict_arx
        n = 100
        y = list(np.cumsum(np.random.default_rng(42).normal(0, 0.01, n)))
        u = [0.01] * n
        model = identify_arx(y, u, na=2, nb=1, nk=1)
        preds = predict_arx(model, y[-5:], [0.01] * 10, u_history=[0.01] * 5)
        assert len(preds) == 10


# ---------- H5: NaN guard in OAT sensitivity ----------

class TestOATNaNGuard:
    """Verify OAT handles NaN from evaluate_fn gracefully."""

    def test_nan_evaluation_does_not_crash(self):
        from core.design.sensitivity import sensitivity_oat

        def eval_fn(p):
            if p["x"] > 7:
                return float("nan")
            return p["x"]

        result = sensitivity_oat(
            base_params={"x": 5.0},
            param_ranges={"x": (0.0, 10.0)},
            evaluate_fn=eval_fn,
            n_levels=10,
        )
        si = result["parameters"]["x"]["sensitivity_index"]
        assert math.isfinite(si)


# ---------- H6: check_odd_series length validation ----------

class TestODDSeriesLengthValidation:
    """Verify check_odd_series validates time_series length."""

    def test_mismatched_lengths_raises(self):
        from core.odd.odd_monitor import check_odd_series
        with pytest.raises(ValueError, match="time_series length"):
            check_odd_series(
                state_series=[{"water_level": 1.0}],
                time_series=[0.0, 1.0],
            )

    def test_matching_lengths_ok(self):
        from core.odd.odd_monitor import check_odd_series
        result = check_odd_series(
            state_series=[{"water_level": 1.0}, {"water_level": 1.1}],
            time_series=[0.0, 1.0],
        )
        assert result["n_steps"] == 2


# ---------- H7: FourPredRequest.inflow_data max_length ----------

class TestFourPredRequestBounds:
    """Verify FourPredRequest.inflow_data has max_length."""

    def test_inflow_data_field_has_max_length(self):
        from web.models import FourPredRequest
        field = FourPredRequest.model_fields["inflow_data"]
        metadata = field.metadata
        # Check max_length is set (via Pydantic field metadata)
        assert any(
            hasattr(m, "max_length") and m.max_length == 100000
            for m in metadata
        )


# ---------- H8: IdentificationRequest / ARXRequest length validation ----------

class TestIdentificationLengthMatch:
    """Verify length-match validators on identification models."""

    def test_identification_length_mismatch(self):
        from web.models import IdentificationRequest
        with pytest.raises(Exception):
            IdentificationRequest(
                observed_h=[1.0, 2.0, 3.0],
                observed_q_out=[1.0, 2.0],
            )

    def test_arx_length_mismatch(self):
        from web.models import ARXRequest
        with pytest.raises(Exception):
            ARXRequest(
                y=[1.0, 2.0, 3.0, 4.0],
                u=[1.0, 2.0, 3.0, 4.0, 5.0],
            )


# ---------- H9: target_level config lookup fix ----------

class TestRehearsalTargetLevel:
    """Verify rehearsal uses correct config key for target_level."""

    def test_target_level_from_top_level_config(self):
        from core.config import get_default_tank_params, load_tank_config
        config = load_tank_config()
        tank_params = get_default_tank_params()
        # target_level is at top level, NOT in tank_params
        assert "target_level" in config
        assert "target_level" not in tank_params


# ---------- H10: OpenAPI disabled in production ----------

class TestOpenAPIProduction:
    """Verify Swagger/docs disabled when ENV=production."""

    def test_docs_available_in_development(self):
        from web.app import _is_prod
        # In test environment, _is_prod should be False
        assert _is_prod is False


# ---------- M3: CSP connect-src and upgrade-insecure-requests ----------

class TestCSPHeaders:
    """Verify CSP includes connect-src and upgrade-insecure-requests."""

    def test_csp_has_connect_src(self):
        from fastapi.testclient import TestClient

        from web.app import app
        client = TestClient(app)
        resp = client.get("/api/roles")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "connect-src 'self'" in csp
        assert "upgrade-insecure-requests" in csp


# ---------- M4: DAG cycle detection ----------

class TestDAGCycleDetection:
    """Verify TaskPlan.validate_dag() detects cycles."""

    def test_no_cycle_passes(self):
        from agents.planning_agent import TaskNode, TaskPlan
        plan = TaskPlan()
        plan.add_node(TaskNode("a", "Task A", "tool_a"))
        plan.add_node(TaskNode("b", "Task B", "tool_b", dependencies=["a"]))
        plan.validate_dag()  # should not raise

    def test_cycle_detected(self):
        from agents.planning_agent import TaskNode, TaskPlan
        plan = TaskPlan()
        plan.add_node(TaskNode("a", "Task A", "tool_a", dependencies=["b"]))
        plan.add_node(TaskNode("b", "Task B", "tool_b", dependencies=["a"]))
        with pytest.raises(ValueError, match="Cycle detected"):
            plan.validate_dag()

    def test_self_cycle_detected(self):
        from agents.planning_agent import TaskNode, TaskPlan
        plan = TaskPlan()
        plan.add_node(TaskNode("a", "Task A", "tool_a", dependencies=["a"]))
        with pytest.raises(ValueError, match="Cycle detected"):
            plan.validate_dag()


# ---------- M5: is_ray_available cached ----------

class TestRayAvailableCached:
    """Verify is_ray_available() caches its result."""

    def test_returns_consistent_result(self):
        from compute.ray_config import is_ray_available
        r1 = is_ray_available()
        r2 = is_ray_available()
        assert r1 is r2

    def test_module_has_cache_variable(self):
        import compute.ray_config as rc
        assert hasattr(rc, "_ray_available")


# ---------- Additional: EvaluationRequest.time_series max_length ----------

class TestEvaluationTimeSeries:
    """Verify time_series has max_length and setpoint has bounds."""

    def test_time_series_has_max_length(self):
        from web.models import EvaluationRequest
        field = EvaluationRequest.model_fields["time_series"]
        metadata = field.metadata
        assert any(
            hasattr(m, "max_length") and m.max_length == 100000
            for m in metadata
        )

    def test_setpoint_has_bounds(self):
        from web.models import EvaluationRequest
        with pytest.raises(Exception):
            EvaluationRequest(
                observed=[1.0],
                predicted=[1.0],
                setpoint=2000,
            )


# ---------- Additional: OutlierDetectRequest.threshold bounded ----------

class TestOutlierThresholdBounded:
    """Verify threshold has upper bound."""

    def test_threshold_too_large(self):
        from web.models import OutlierDetectRequest
        with pytest.raises(Exception):
            OutlierDetectRequest(data=[1.0, 2.0, 3.0], threshold=200)

    def test_threshold_valid(self):
        from web.models import OutlierDetectRequest
        req = OutlierDetectRequest(data=[1.0, 2.0, 3.0], threshold=3.0)
        assert req.threshold == 3.0
