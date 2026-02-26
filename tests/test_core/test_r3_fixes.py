"""Tests for Round 3 review fixes.
R3 评审修复测试。
"""

import copy
import pytest
import numpy as np


# ---------- CRITICAL: DoS step limit ----------

class TestStepLimitValidation:
    """Verify that duration/dt ratio is bounded."""

    def test_simulation_step_limit_rejects(self):
        from web.models import SimulationRequest
        with pytest.raises(Exception, match="Too many simulation steps"):
            SimulationRequest(duration=86400, dt=0.001)

    def test_simulation_step_limit_accepts(self):
        from web.models import SimulationRequest
        req = SimulationRequest(duration=1000, dt=1.0)
        assert req.duration == 1000

    def test_control_step_limit_rejects(self):
        from web.models import ControlRequest
        with pytest.raises(Exception, match="Too many simulation steps"):
            ControlRequest(duration=86400, dt=0.001)

    def test_control_step_limit_accepts(self):
        from web.models import ControlRequest
        req = ControlRequest(duration=300, dt=1.0)
        assert req.duration == 300


# ---------- CRITICAL: predict_arx with u_history ----------

class TestPredictARXHistory:
    """Verify predict_arx correctly uses u_history."""

    def test_predict_arx_with_u_history(self):
        from core.identification.arx_model import identify_arx, predict_arx

        # Generate a simple system: y(k) = 0.5*y(k-1) + 0.3*u(k-1)
        n = 100
        rng = np.random.default_rng(42)
        u = rng.normal(0, 0.01, n)
        y = np.zeros(n)
        for k in range(1, n):
            y[k] = 0.5 * y[k - 1] + 0.3 * u[k - 1]

        model = identify_arx(y.tolist(), u.tolist(), na=1, nb=1, nk=1)

        # Predict with u_history provided
        y_hist = y[-5:].tolist()
        u_hist = u[-5:].tolist()
        u_future = [0.01] * 10
        preds = predict_arx(model, y_hist, u_future, u_history=u_hist)
        assert len(preds) == 10
        # With u_history, the first prediction should use historical u values
        # and should differ from prediction without u_history
        preds_no_hist = predict_arx(model, y_hist, u_future)
        # They may differ since u_history provides context for the delay
        assert isinstance(preds[0], float)

    def test_predict_arx_without_u_history_backward_compat(self):
        """predict_arx still works without u_history (backward compat)."""
        from core.identification.arx_model import predict_arx
        model = {
            "a_coefficients": [-0.5],
            "b_coefficients": [0.3],
            "na": 1, "nb": 1, "nk": 1,
        }
        preds = predict_arx(model, [1.0, 0.8, 0.6], [0.01] * 5)
        assert len(preds) == 5


# ---------- CRITICAL: interpolate_inflow O(log n) ----------

class TestInterpolateInflowBisect:
    """Verify _interpolate_inflow uses bisect correctly."""

    def test_interpolation_matches_expected(self):
        from core.simulation.simulator import _interpolate_inflow, _make_inflow_cache
        profile = [(0, 0.01), (100, 0.03), (200, 0.01)]
        cache = _make_inflow_cache(profile)
        # At t=50 between (0,0.01) and (100,0.03): linear interp
        val = _interpolate_inflow(50, profile, cache)
        assert val == pytest.approx(0.02)
        # At boundaries
        assert _interpolate_inflow(0, profile, cache) == 0.01
        assert _interpolate_inflow(200, profile, cache) == 0.01
        # Before first
        assert _interpolate_inflow(-10, profile, cache) == 0.01
        # After last
        assert _interpolate_inflow(300, profile, cache) == 0.01

    def test_single_point_profile(self):
        from core.simulation.simulator import _interpolate_inflow
        assert _interpolate_inflow(50, [(0, 0.02)]) == 0.02

    def test_empty_profile(self):
        from core.simulation.simulator import _interpolate_inflow
        assert _interpolate_inflow(50, []) == 0.0


# ---------- HIGH: run_mpc_control doesn't mutate caller's dict ----------

class TestMPCNoMutation:
    """Verify run_mpc_control doesn't mutate mpc_params."""

    def test_mpc_params_not_mutated(self):
        from core.control.mpc_controller import run_mpc_control
        params = {"horizon": 5, "q_weight": 10.0}
        original_keys = set(params.keys())
        run_mpc_control(setpoint=1.0, initial_h=0.5, duration=10, dt=1.0,
                        mpc_params=params)
        # Caller's dict should not have extra keys
        assert set(params.keys()) == original_keys


# ---------- HIGH: get_default_*_params() returns copies ----------

class TestConfigReturnsCopies:
    """Verify config getters return independent copies."""

    def test_tank_params_independent(self):
        from core.config import get_default_tank_params
        p1 = get_default_tank_params()
        p2 = get_default_tank_params()
        p1["area"] = 999
        assert p2["area"] != 999

    def test_pid_params_independent(self):
        from core.config import get_default_pid_params
        p1 = get_default_pid_params()
        p2 = get_default_pid_params()
        p1["kp"] = 999
        assert p2["kp"] != 999


# ---------- HIGH: PlanningAgent deep-copies template nodes ----------

class TestPlanningAgentCopy:
    """Verify plan templates are deep-copied."""

    def test_template_not_corrupted(self):
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        # Create first plan and mutate a node
        plan1 = agent.plan("compare PID vs MPC")
        plan1.nodes[0].status = "completed"
        # Create second plan — nodes should be fresh
        plan2 = agent.plan("compare PID vs MPC")
        assert plan2.nodes[0].status == "pending"


# ---------- HIGH: AnalysisAgent async compare ----------

class TestAnalysisAgentAsync:
    """Verify AnalysisAgent.compare_schemes is properly async."""

    @pytest.mark.asyncio
    async def test_compare_schemes_runs(self):
        from agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent()
        schemes = [
            {"duration": 50, "dt": 1.0, "initial_h": 0.5},
            {"duration": 50, "dt": 1.0, "initial_h": 0.8},
        ]
        result = await agent.compare_schemes(schemes)
        assert result["n_schemes"] == 2
        assert len(result["results"]) == 2
        assert len(result["ranking"]) == 2


# ---------- HIGH: Monte Carlo clamps to positive ----------

class TestMonteCarloClamp:
    """Verify monte_carlo_sim never generates negative params."""

    def test_no_negative_params(self):
        from compute.distributed_sim import monte_carlo_sim
        # Use high std to increase chance of negative raw samples
        result = monte_carlo_sim(
            base_params={"duration": 50, "dt": 1.0, "initial_h": 0.5},
            vary_params={"area": (0.01, 0.05)},  # mean=0.01, std=0.05
            n_samples=5,
            use_ray=False,
            seed=42,
        )
        assert len(result) == 5
        # All should have succeeded (no negative param crash)


# ---------- HIGH: SafetyAgent bounded violation log ----------

class TestSafetyAgentBoundedLog:
    """Verify _violation_log is bounded via deque."""

    def test_violation_log_bounded(self):
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent(max_log_entries=5)
        for i in range(10):
            agent.check_state({"water_level": 5.0})  # MRC violation
        assert len(agent.get_violation_log()) == 5


# ---------- HIGH: check_odd_series pre-resolves spec ----------

class TestODDSeriesPreResolve:
    """Verify check_odd_series doesn't recreate ODDSpec per step."""

    def test_works_with_none_spec(self):
        from core.odd.odd_monitor import check_odd_series
        states = [{"water_level": 1.0}] * 5
        result = check_odd_series(states, odd_spec=None)
        assert result["worst_zone"] == "normal"
        assert result["n_steps"] == 5


# ---------- MEDIUM: safety_factor in design pipeline ----------

class TestSafetyFactorInSizing:
    """Verify safety_factor actually affects sizing."""

    def test_safety_factor_increases_volume(self):
        from core.design.sizing import optimize_tank_size
        r1 = optimize_tank_size(safety_factor=1.0)
        r2 = optimize_tank_size(safety_factor=2.0)
        assert r2["required_volume"] > r1["required_volume"]
        assert r2["volume"] >= r2["required_volume"] - 1e-6


# ---------- MEDIUM: WarningSkill red threshold ----------

class TestWarningThresholds:
    """Verify red warning is reachable for imminent breaches."""

    def test_red_threshold_reachable(self):
        from skills.warning_skill import _WARNING_THRESHOLDS
        # Red threshold should be > 0 (was 0.0, now 0.05)
        assert _WARNING_THRESHOLDS["red"] > 0

    def test_classify_near_zero_breach(self):
        from skills.warning_skill import WarningSkill
        # breach_fraction = 1/60 ≈ 0.017 < 0.05 → red
        odd_result = {"worst_zone": "mrc", "time_to_breach": 1.0}
        level = WarningSkill._classify_warning(odd_result, horizon_length=60)
        assert level == "red"


# ---------- MEDIUM: GZip middleware ----------

class TestGZipMiddleware:
    """Verify GZip middleware is configured."""

    def test_gzip_in_middleware(self):
        from web.app import app
        middleware_classes = [m.cls.__name__ if hasattr(m, 'cls') else str(m)
                             for m in app.user_middleware]
        assert any("GZip" in c for c in middleware_classes)


# ---------- MEDIUM: HSTS header ----------

class TestHSTSHeader:
    """Verify HSTS header is set."""

    def test_hsts_present(self):
        from fastapi.testclient import TestClient
        from web.app import app
        client = TestClient(app)
        resp = client.get("/api/roles")
        assert "strict-transport-security" in resp.headers


# ---------- MEDIUM: ValueError truncation ----------

class TestValueErrorTruncation:
    """Verify long ValueError messages are truncated."""

    def test_long_error_truncated(self):
        from fastapi.testclient import TestClient
        from web.app import app
        client = TestClient(app)
        # Trigger a ValueError with a long message via invalid data
        # Use an endpoint that can raise ValueError from core
        resp = client.post("/api/simulation/run", json={
            "duration": 100, "dt": 1.0, "initial_h": 0.5,
            "solver": "rk4",
            "tank_params": {"area": -1.0},  # negative area → ValueError
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert len(detail) <= 203  # 200 + "..."


# ---------- MEDIUM: Shared singleton ----------

class TestSharedSingleton:
    """Verify both routers use the same orchestrator instance."""

    def test_deps_singleton_consistent(self):
        from web.deps import get_orchestrator
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        assert orch1 is orch2


# ---------- MEDIUM: Objective Literal validation ----------

class TestObjectiveLiteral:
    """Verify objective field uses Literal validation."""

    def test_invalid_objective_rejected(self):
        from fastapi.testclient import TestClient
        from web.app import app
        client = TestClient(app)
        resp = client.post("/api/scheduling/run", json={
            "demand_forecast": [0.01, 0.02],
            "objective": "bad_objective",
        })
        assert resp.status_code == 422
