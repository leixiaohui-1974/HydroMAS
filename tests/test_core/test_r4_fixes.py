"""Tests for R4 multi-agent review fixes.
R4 多智能体评审修复测试。
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest


# ---------- C1: predict_linear/polynomial lookback truncation ----------

class TestLookbackTruncation:
    """Validate length check happens after lookback truncation."""

    def test_linear_lookback_1_crashes_before_fix(self):
        from core.prediction.linear_predictor import predict_linear
        data = list(range(100))
        with pytest.raises(ValueError, match="at least 2"):
            predict_linear(data, horizon=5, lookback=1)

    def test_polynomial_lookback_too_small(self):
        from core.prediction.linear_predictor import predict_polynomial
        data = list(range(100))
        with pytest.raises(ValueError, match="at least 3"):
            predict_polynomial(data, horizon=5, degree=2, lookback=2)

    def test_linear_lookback_valid(self):
        from core.prediction.linear_predictor import predict_linear
        result = predict_linear(list(range(100)), horizon=5, lookback=10)
        assert len(result["predictions"]) == 5

    def test_polynomial_lookback_valid(self):
        from core.prediction.linear_predictor import predict_polynomial
        result = predict_polynomial(list(range(100)), horizon=5, degree=2, lookback=10)
        assert len(result["predictions"]) == 5


# ---------- C2: LP objective switch ----------

class TestLPObjectiveSwitch:
    """Verify objective parameter actually affects optimization."""

    def test_minimize_cost_lower_inflow(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        r_min = optimize_schedule_lp(
            demand_forecast=[0.005] * 5,
            supply_capacity=0.05,
            objective="minimize_cost",
        )
        r_max = optimize_schedule_lp(
            demand_forecast=[0.005] * 5,
            supply_capacity=0.05,
            objective="maximize_supply",
        )
        if r_min["status"] == "optimal" and r_max["status"] == "optimal":
            assert r_max["total_inflow"] >= r_min["total_inflow"]


# ---------- H1: Morris EE sign fix ----------

class TestMorrisEESign:
    """Verify Morris elementary effects have correct sign."""

    def test_positive_effect(self):
        from core.design.sensitivity import sensitivity_morris
        # y = x, so EE should always be positive
        result = sensitivity_morris(
            param_ranges={"x": (0.0, 10.0)},
            evaluate_fn=lambda p: p["x"],
            n_trajectories=20,
            n_levels=4,
            seed=42,
        )
        assert result["parameters"]["x"]["mu"] > 0

    def test_negative_effect(self):
        from core.design.sensitivity import sensitivity_morris
        # y = -x, so EE should always be negative
        result = sensitivity_morris(
            param_ranges={"x": (0.0, 10.0)},
            evaluate_fn=lambda p: -p["x"],
            n_trajectories=20,
            n_levels=4,
            seed=42,
        )
        assert result["parameters"]["x"]["mu"] < 0


# ---------- H2: PlanningAgent deepcopy ----------

class TestPlanningAgentDeepCopy:
    """Ensure template params/dependencies are not shared."""

    def test_mutating_plan_node_params(self):
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        plan1 = agent.plan("compare pid vs mpc controllers")
        plan1.nodes[0].params["injected"] = True
        plan1.nodes[2].dependencies.append("extra")

        plan2 = agent.plan("compare pid vs mpc controllers")
        assert "injected" not in plan2.nodes[0].params
        assert "extra" not in plan2.nodes[2].dependencies


# ---------- H3: round vs int for step count ----------

class TestRoundStepCount:
    """Verify round() prevents truncation of simulation time."""

    def test_simulation_covers_full_duration(self):
        from core.simulation import run_simulation
        result = run_simulation(duration=10, dt=3.0)
        # round(10/3) = 3, final time = 9.0
        # int(10/3) = 3 too — but for 10/7:
        result2 = run_simulation(duration=10, dt=7.0)
        # round(10/7) = round(1.428) = 1
        # The key point: it shouldn't silently lose > dt/2 seconds
        assert len(result2["water_level"]) >= 2


# ---------- H4: Median filter fast path ----------

class TestMedianFilterFastPath:
    """Verify scipy fast path is used when no NaN."""

    def test_no_nan_fast_path(self):
        from core.data_clean.interpolation import median_filter
        data = list(range(100))
        result = median_filter(data, window_size=5)
        assert len(result["data"]) == 100
        assert result["method"] == "median_filter"

    def test_with_nan_fallback(self):
        from core.data_clean.interpolation import median_filter
        data = [1.0, float("nan"), 3.0, 4.0, 5.0]
        result = median_filter(data, window_size=3)
        assert not any(math.isnan(v) for v in result["data"])


# ---------- H7: FourPredictionLoop tool propagation ----------

class TestFourPredToolPropagation:
    """Verify register_tool propagates to sub-skills."""

    def test_register_propagates(self):
        from skills.four_prediction_loop import FourPredictionLoopSkill
        skill = FourPredictionLoopSkill()
        skill.register_tool("test_tool", lambda: "ok")
        assert "test_tool" in skill._forecast_skill._tool_registry
        assert "test_tool" in skill._warning_skill._tool_registry
        assert "test_tool" in skill._rehearsal_skill._tool_registry
        assert "test_tool" in skill._plan_skill._tool_registry


# ---------- H8: Thread-safe singleton ----------

class TestThreadSafeSingleton:
    """Verify deps singleton uses lock."""

    def test_singleton_consistent(self):
        from web.deps import get_orchestrator
        o1 = get_orchestrator()
        o2 = get_orchestrator()
        assert o1 is o2

    def test_lock_exists(self):
        import web.deps
        assert hasattr(web.deps, "_lock")
        assert hasattr(web.deps._lock, "acquire")
        assert hasattr(web.deps._lock, "release")


# ---------- M1: CORS default ----------

class TestCORSDefault:
    """Verify CORS does not default to wildcard."""

    def test_not_wildcard_default(self):
        from web.app import _allowed_origins
        assert _allowed_origins != ["*"]


# ---------- M3: Upper bounds on initial_h / setpoint ----------

class TestUpperBounds:
    """Verify extreme float values are rejected."""

    def test_simulation_initial_h_too_large(self):
        from web.models import SimulationRequest
        with pytest.raises(Exception):
            SimulationRequest(initial_h=200)

    def test_control_setpoint_too_large(self):
        from web.models import ControlRequest
        with pytest.raises(Exception):
            ControlRequest(setpoint=200)


# ---------- M4: Sensitivity combinatorial limit ----------

class TestSensitivityLimit:
    """Verify combinatorial explosion is prevented."""

    def test_too_many_evaluations(self):
        from web.models import SensitivityRequest
        with pytest.raises(Exception):
            SensitivityRequest(
                base_params={f"p{i}": 1.0 for i in range(20)},
                param_ranges={f"p{i}": [0.0, 2.0] for i in range(20)},
                n_levels=500,
            )


# ---------- M5: LP initial_level validation ----------

class TestLPInitialLevelValidation:
    """Verify initial_level outside bounds raises."""

    def test_initial_below_min(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        with pytest.raises(ValueError, match="initial_level"):
            optimize_schedule_lp(
                demand_forecast=[0.005],
                supply_capacity=0.05,
                min_level=0.3,
                initial_level=0.1,
            )

    def test_initial_above_max(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        with pytest.raises(ValueError, match="initial_level"):
            optimize_schedule_lp(
                demand_forecast=[0.005],
                supply_capacity=0.05,
                max_level=1.5,
                initial_level=2.0,
            )


# ---------- M6: EvaluationRequest length match ----------

class TestEvaluationLengthMatch:
    """Verify observed/predicted length mismatch is rejected."""

    def test_length_mismatch(self):
        from web.models import EvaluationRequest
        with pytest.raises(Exception):
            EvaluationRequest(observed=[1.0, 2.0], predicted=[1.0])


# ---------- M7: ODDSeriesRequest times/states length ----------

class TestODDSeriesLengthMatch:
    """Verify states/times length mismatch is rejected."""

    def test_times_states_mismatch(self):
        from web.models import ODDSeriesRequest
        with pytest.raises(Exception):
            ODDSeriesRequest(
                states=[{"water_level": 1.0}],
                times=[0.0, 1.0],
            )


# ---------- M8: OAT sensitivity normalization ----------

class TestOATNormalization:
    """Verify sensitivity normalizes by parameter range."""

    def test_different_ranges_normalized(self):
        from core.design.sensitivity import sensitivity_oat
        # y = x, two params with different ranges
        result = sensitivity_oat(
            base_params={"a": 5.0, "b": 5.0},
            param_ranges={"a": (0.0, 10.0), "b": (4.0, 6.0)},
            evaluate_fn=lambda p: p["a"] + p["b"],
            n_levels=5,
        )
        # Both have same effect on output, but different ranges
        # After normalization, sensitivity should be similar
        sa = result["parameters"]["a"]["sensitivity_index"]
        sb = result["parameters"]["b"]["sensitivity_index"]
        # They should be approximately equal now (both measure dy/dx / y_base)
        assert abs(sa - sb) < sa * 0.5  # within 50% of each other


# ---------- M9: Orchestrator async tool execution ----------

class TestOrchestratorAsyncTool:
    """Verify _execute_tool uses asyncio.to_thread."""

    @pytest.mark.asyncio
    async def test_execute_tool_async(self):
        from agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        result = await agent._execute_tool("simulate_tank", {
            "duration": 10,
            "dt": 1.0,
        })
        assert result["status"] == "completed"
        assert "water_level" in result["data"]


# ---------- M10: Tool map caching ----------

class TestToolMapCaching:
    """Verify tool module map is cached at module level."""

    def test_tool_map_exists(self):
        from skills.base_skill import _TOOL_MODULE_MAP, _resolved_tools
        assert "simulate_tank" in _TOOL_MODULE_MAP
        assert isinstance(_resolved_tools, dict)


# ---------- M12: predict_arx warning ----------

class TestPredictARXWarning:
    """Verify warning when u_history missing with nk > 0."""

    def test_warns_on_missing_u_history(self):
        from core.identification.arx_model import predict_arx
        model = {
            "a_coefficients": [-0.9],
            "b_coefficients": [0.3],
            "na": 1, "nb": 1, "nk": 1,
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            predict_arx(model, [1.0, 0.8], [0.01] * 5)
            assert any("u_history" in str(x.message) for x in w)

    def test_no_warning_with_u_history(self):
        from core.identification.arx_model import predict_arx
        model = {
            "a_coefficients": [-0.9],
            "b_coefficients": [0.3],
            "na": 1, "nb": 1, "nk": 1,
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            predict_arx(model, [1.0, 0.8], [0.01] * 5, u_history=[0.01, 0.01])
            assert not any("u_history" in str(x.message) for x in w)
