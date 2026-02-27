"""Final coverage tests — filling remaining gaps across all layers.
最终覆盖率测试 — 补齐所有层的遗漏。
"""

import numpy as np
import pytest

# ---------- CSV Data Loader ----------

class TestSampleTimeseries:
    """Test loading sample_timeseries.csv via config loader."""

    def test_load_sample_timeseries(self):
        from core.config import load_sample_timeseries
        data = load_sample_timeseries()
        assert "time" in data
        assert "inflow" in data
        assert "water_level" in data
        assert "water_level_observed" in data
        assert len(data["time"]) == 600

    def test_data_types_are_floats(self):
        from core.config import load_sample_timeseries
        data = load_sample_timeseries()
        for col in data.values():
            for v in col[:5]:
                assert isinstance(v, float)

    def test_time_starts_at_zero(self):
        from core.config import load_sample_timeseries
        data = load_sample_timeseries()
        assert data["time"][0] == 0.0

    def test_import_from_core(self):
        from core import load_sample_timeseries
        data = load_sample_timeseries()
        assert len(data["water_level"]) == 600

    def test_data_usable_with_prediction(self):
        """Sample data can be used directly with predict_linear."""
        from core.config import load_sample_timeseries
        from core.prediction import predict_linear
        data = load_sample_timeseries()
        result = predict_linear(data["water_level"], horizon=10)
        assert len(result["predictions"]) == 10

    def test_data_usable_with_evaluation(self):
        """Observed vs simulated from CSV can be evaluated."""
        from core.config import load_sample_timeseries
        from core.evaluation import evaluate_performance
        data = load_sample_timeseries()
        result = evaluate_performance(
            data["water_level"][:100],
            data["water_level_observed"][:100],
            metrics_list=["RMSE", "MAE", "NSE"],
        )
        assert "RMSE" in result
        assert "NSE" in result
        assert result["NSE"] > 0  # Reasonable fit expected

    def test_data_usable_with_identification(self):
        """Sample data can be used for tank parameter identification."""
        from core.config import load_sample_timeseries
        from core.identification import identify_tank_params
        data = load_sample_timeseries()
        result = identify_tank_params(
            observed_h=data["water_level"][:100],
            observed_q_out=[abs(v) for v in data["inflow"][:100]],
        )
        assert result["converged"]
        assert result["cd"] > 0


# ---------- MCP Server Additional Tests ----------

class TestPredictionServerLSTM:
    """Test prediction server with LSTM model."""

    def test_lstm_model_via_server(self):
        import pytest

        from mcp_servers.prediction_server import predict_future
        with pytest.raises(ValueError, match="torch not installed"):
            predict_future(
                historical_data=[0.5 + 0.001 * i for i in range(100)],
                horizon=10,
                model="lstm",
            )


class TestDesignServerMorris:
    """Test design server Morris sensitivity analysis."""

    def test_morris_sensitivity(self):
        from mcp_servers.design_server import run_sensitivity
        result = run_sensitivity(
            base_params={"area": 1.0, "cd": 0.6},
            param_ranges={"area": [0.5, 1.5], "cd": [0.3, 0.9]},
            method="Morris",
            n_levels=4,
        )
        assert result["method"] == "Morris"
        assert "area" in result["parameters"]
        assert "mu_star" in result["parameters"]["area"]


class TestODDServerExtended:
    """Extended ODD server tests."""

    def test_check_odd_with_custom_config(self):
        """Check ODD with custom config dict."""
        from mcp_servers.odd_server import check_odd
        custom = {
            "dimensions": [
                {"name": "water_level", "min_value": 0.0, "max_value": 1.0, "unit": "m"},
            ]
        }
        result = check_odd(
            current_state={"water_level": 1.5},
            odd_config=custom,
        )
        assert result["zone"] == "mrc"

    def test_check_odd_instant_mode_explicit(self):
        from mcp_servers.odd_server import check_odd
        result = check_odd(
            current_state={"water_level": 1.0},
            check_mode="instant",
        )
        assert result["zone"] == "normal"


class TestIdentificationServerExtended:
    """Extended identification server tests."""

    def test_nonlinear_with_initial_guess(self):
        from mcp_servers.identification_server import identify_parameters
        h = np.linspace(0.2, 1.5, 50)
        q = 0.6 * 0.01 * np.sqrt(2 * 9.81 * h)
        result = identify_parameters(
            observed_h=h.tolist(),
            observed_q_out=q.tolist(),
            model_type="nonlinear",
            initial_guess={"cd": 0.5, "outlet_area": 0.008},
        )
        assert result["converged"]
        assert abs(result["cd"] - 0.6) < 0.15


# ---------- Compute Module Additional Tests ----------

class TestComputeActorController:
    """Test actor_controller module."""

    def test_create_mpc_actor_local(self):
        """MPC actor should work locally when Ray unavailable."""
        from compute.actor_controller import create_mpc_actor
        actor = create_mpc_actor(horizon=5, tank_area=1.0, dt=1.0)
        assert actor is not None
        # Should have compute method
        u = actor.compute(current_h=0.5, setpoint=1.0)
        assert isinstance(u, float)
        assert u >= 0


class TestComputeRayConfig:
    """Test ray_config module edge cases."""

    def test_is_ray_available(self):
        from compute.ray_config import is_ray_available
        # Should return bool regardless of Ray installation
        result = is_ray_available()
        assert isinstance(result, bool)

    def test_shutdown_without_init(self):
        """shutdown_ray should be safe to call without init."""
        from compute.ray_config import shutdown_ray
        shutdown_ray()  # Should not raise


# ---------- Evaluation Module Additional Tests ----------

class TestEvaluationExtended:
    """Extended evaluation metric tests."""

    def test_settling_time_never_settles(self):
        """If value never settles, return None."""
        from core.evaluation.metrics import settling_time
        # Values that keep oscillating
        values = [0.0, 2.0, 0.0, 2.0, 0.0, 2.0]
        time = [0, 1, 2, 3, 4, 5]
        result = settling_time(time, values, setpoint=1.0)
        assert result is None

    def test_settling_time_already_settled(self):
        """If already at setpoint, settling_time is 0."""
        from core.evaluation.metrics import settling_time
        values = [1.0, 1.0, 1.0, 1.0]
        time = [0, 1, 2, 3]
        result = settling_time(time, values, setpoint=1.0)
        assert result == 0.0

    def test_overshoot_no_overshoot(self):
        """If response never exceeds setpoint, overshoot is 0."""
        from core.evaluation.metrics import overshoot
        values = [0.0, 0.5, 0.8, 0.95, 1.0]
        result = overshoot(values, setpoint=1.0)
        assert result == 0.0

    def test_overshoot_with_overshoot(self):
        """Compute correct overshoot percentage."""
        from core.evaluation.metrics import overshoot
        values = [0.0, 0.5, 1.2, 1.0, 1.0]  # max 1.2 vs setpoint 1.0
        result = overshoot(values, setpoint=1.0)
        assert result == pytest.approx(20.0)

    def test_steady_state_error(self):
        """Compute SSE from tail average."""
        from core.evaluation.metrics import steady_state_error
        values = [0.5, 0.8, 0.95, 1.02, 1.01, 1.0, 0.99, 1.01, 1.0, 1.0]
        result = steady_state_error(values, setpoint=1.0, n_tail=5)
        assert abs(result) < 0.02

    def test_nse_perfect_prediction(self):
        """Perfect prediction should give NSE = 1."""
        from core.evaluation.metrics import nse
        obs = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = nse(obs, obs)
        assert result == 1.0

    def test_mape_with_zeros(self):
        """MAPE should handle zeros in observed."""
        from core.evaluation.metrics import mape
        obs = [0.0, 1.0, 2.0, 0.0]
        pred = [0.1, 1.1, 2.1, 0.1]
        result = mape(obs, pred)
        # Should only compute MAPE for non-zero observed values
        assert result > 0


# ---------- Simulation Extended Tests ----------

class TestSimulationExtended:
    """Extended simulation edge cases."""

    def test_euler_vs_rk4_similar(self):
        """Euler and RK4 should give similar results for small dt."""
        from core.simulation import run_simulation
        euler = run_simulation(duration=60, dt=0.1, initial_h=0.5, solver="euler")
        rk4 = run_simulation(duration=60, dt=0.1, initial_h=0.5, solver="rk4")
        euler_final = euler["water_level"][-1]
        rk4_final = rk4["water_level"][-1]
        assert abs(euler_final - rk4_final) < 0.01

    def test_unknown_solver_raises(self):
        """Unknown solver type should raise ValueError."""
        from core.simulation import run_simulation
        with pytest.raises(ValueError, match="Unknown solver"):
            run_simulation(duration=10, solver="midpoint")

    def test_inflow_profile_interpolation(self):
        """Inflow profile should be correctly interpolated."""
        from core.simulation import run_simulation
        result = run_simulation(
            duration=100,
            dt=1.0,
            q_in_profile=[(0, 0.01), (50, 0.03), (100, 0.01)],
            initial_h=0.5,
        )
        # Water level should rise in the first half (more inflow)
        mid_idx = 50
        assert result["water_level"][mid_idx] > result["water_level"][0]


# ---------- WNAL Assessment Extended ----------

class TestWNALExtended:
    """Extended WNAL assessment tests."""

    def test_full_marks_gives_l5(self):
        from core.evaluation import assess_wnal
        caps = {k: 100.0 for k in [
            "sensing", "communication", "modeling",
            "prediction", "control", "odd_monitoring", "decision_support",
        ]}
        result = assess_wnal(caps)
        assert result["level"] == "L5"
        assert result["score"] == 100.0

    def test_zero_marks_gives_l0(self):
        from core.evaluation import assess_wnal
        result = assess_wnal({})
        assert result["level"] == "L0"
        assert result["score"] == 0.0
        assert len(result["gaps"]) > 0

    def test_recommendations_for_low_level(self):
        from core.evaluation import assess_wnal
        caps = {"sensing": 30, "control": 20}
        result = assess_wnal(caps)
        assert len(result["recommendations"]) > 0
        assert any("ODD" in r for r in result["recommendations"])


# ---------- Four Prediction Loop Extended ----------

class TestFourPredictionLoopExtended:
    """Extended tests for the 四预 loop skill."""

    @pytest.mark.asyncio
    async def test_loop_with_no_data(self):
        """Loop should fail gracefully with empty data."""
        from skills.four_prediction_loop import FourPredictionLoopSkill
        skill = FourPredictionLoopSkill()
        result = await skill.run({"historical_data": []})
        assert not result.success
        assert "No historical_data" in result.error

    @pytest.mark.asyncio
    async def test_loop_with_low_risk_data(self):
        """Loop with normal data should stop at warning (no rehearsal)."""
        from skills.four_prediction_loop import FourPredictionLoopSkill
        skill = FourPredictionLoopSkill()
        # Flat low-risk data — should result in green/blue warning
        data = [0.5 + 0.001 * i for i in range(120)]
        result = await skill.run({
            "historical_data": data,
            "horizon": 10,
        })
        assert result.success
        assert "forecast" in result.steps_completed
        assert "warning" in result.steps_completed
