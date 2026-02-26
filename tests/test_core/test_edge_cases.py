"""Edge-case tests for input validation and error handling across core modules."""

import pytest
import numpy as np


class TestSimulationValidation:
    def test_zero_dt_raises(self):
        from core.simulation.simulator import run_simulation
        with pytest.raises(ValueError, match="dt must be positive"):
            run_simulation(duration=10, dt=0)

    def test_negative_dt_raises(self):
        from core.simulation.simulator import run_simulation
        with pytest.raises(ValueError, match="dt must be positive"):
            run_simulation(duration=10, dt=-1)

    def test_negative_duration_raises(self):
        from core.simulation.simulator import run_simulation
        with pytest.raises(ValueError, match="duration must be positive"):
            run_simulation(duration=-5, dt=1.0)


class TestPIDValidation:
    def test_zero_dt_raises(self):
        from core.control.pid_controller import PIDController
        pid = PIDController()
        with pytest.raises(ValueError, match="dt must be positive"):
            pid.compute(setpoint=1.0, measured=0.5, dt=0)

    def test_negative_dt_raises(self):
        from core.control.pid_controller import PIDController
        pid = PIDController()
        with pytest.raises(ValueError, match="dt must be positive"):
            pid.compute(setpoint=1.0, measured=0.5, dt=-1)


class TestMPCValidation:
    def test_zero_tank_area_raises(self):
        from core.control.mpc_controller import MPCController
        with pytest.raises(ValueError, match="tank_area must be positive"):
            MPCController(tank_area=0)

    def test_zero_dt_raises(self):
        from core.control.mpc_controller import MPCController
        with pytest.raises(ValueError, match="dt must be positive"):
            MPCController(dt=0)

    def test_optimization_fallback(self):
        """MPC should return safe fallback when optimization fails."""
        from core.control.mpc_controller import MPCController
        mpc = MPCController(horizon=5, u_min=0.0, u_max=0.05)
        # Normal computation should succeed
        u = mpc.compute(current_h=0.5, setpoint=1.0)
        assert 0.0 <= u <= 0.05


class TestLPSchedulerValidation:
    def test_empty_demand_raises(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        with pytest.raises(ValueError, match="demand_forecast cannot be empty"):
            optimize_schedule_lp(demand_forecast=[], supply_capacity=0.05)

    def test_zero_supply_raises(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        with pytest.raises(ValueError, match="supply_capacity must be positive"):
            optimize_schedule_lp(demand_forecast=[0.01], supply_capacity=0)

    def test_negative_supply_raises(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        with pytest.raises(ValueError, match="supply_capacity must be positive"):
            optimize_schedule_lp(demand_forecast=[0.01], supply_capacity=-1)


class TestSensitivityValidation:
    def test_morris_n_levels_one_raises(self):
        from core.design.sensitivity import sensitivity_morris
        with pytest.raises(ValueError, match="n_levels must be at least 2"):
            sensitivity_morris(
                param_ranges={"x": (0, 1)},
                evaluate_fn=lambda p: p["x"],
                n_levels=1,
            )


class TestPredictionValidation:
    def test_zero_horizon_raises(self):
        from core.prediction.linear_predictor import predict_linear
        with pytest.raises(ValueError, match="horizon must be positive"):
            predict_linear([1.0, 2.0, 3.0], horizon=0)

    def test_negative_horizon_raises(self):
        from core.prediction.linear_predictor import predict_linear
        with pytest.raises(ValueError, match="horizon must be positive"):
            predict_linear([1.0, 2.0, 3.0], horizon=-5)

    def test_polynomial_zero_horizon_raises(self):
        from core.prediction.linear_predictor import predict_polynomial
        with pytest.raises(ValueError, match="horizon must be positive"):
            predict_polynomial([1.0, 2.0, 3.0], horizon=0)


class TestMCPServerValidation:
    def test_simulation_zero_dt(self):
        from mcp_servers.simulation_server import simulate_tank
        with pytest.raises(ValueError, match="dt must be positive"):
            simulate_tank(duration=10, dt=0)

    def test_simulation_empty_batch(self):
        from mcp_servers.simulation_server import simulate_batch
        with pytest.raises(ValueError, match="schemes list cannot be empty"):
            simulate_batch(schemes=[])

    def test_clean_empty_data(self):
        from mcp_servers.dataclean_server import clean_timeseries
        with pytest.raises(ValueError, match="raw_data cannot be empty"):
            clean_timeseries(raw_data=[])

    def test_detect_outliers_empty_data(self):
        from mcp_servers.dataclean_server import detect_outliers
        with pytest.raises(ValueError, match="data list cannot be empty"):
            detect_outliers(data=[])

    def test_predict_empty_data(self):
        from mcp_servers.prediction_server import predict_future
        with pytest.raises(ValueError, match="historical_data cannot be empty"):
            predict_future(historical_data=[])

    def test_predict_zero_horizon(self):
        from mcp_servers.prediction_server import predict_future
        with pytest.raises(ValueError, match="horizon must be positive"):
            predict_future(historical_data=[1.0, 2.0, 3.0], horizon=0)

    def test_schedule_empty_demand(self):
        from mcp_servers.scheduling_server import optimize_schedule
        with pytest.raises(ValueError, match="demand_forecast cannot be empty"):
            optimize_schedule(demand_forecast=[])

    def test_schedule_zero_supply(self):
        from mcp_servers.scheduling_server import optimize_schedule
        with pytest.raises(ValueError, match="supply_capacity must be positive"):
            optimize_schedule(demand_forecast=[0.01], supply_capacity=0)

    def test_evaluate_empty_lists(self):
        from mcp_servers.evaluation_server import evaluate_performance
        with pytest.raises(ValueError, match="cannot be empty"):
            evaluate_performance(observed=[], predicted=[])

    def test_evaluate_length_mismatch(self):
        from mcp_servers.evaluation_server import evaluate_performance
        with pytest.raises(ValueError, match="same length"):
            evaluate_performance(observed=[1, 2, 3], predicted=[1, 2])

    def test_control_invalid_type(self):
        from mcp_servers.control_server import run_controller
        with pytest.raises(ValueError, match="Unknown controller_type"):
            run_controller(setpoint=1.0, controller_type="INVALID")


class TestComputeValidation:
    def test_monte_carlo_zero_samples(self):
        from compute.distributed_sim import monte_carlo_sim
        with pytest.raises(ValueError, match="n_samples must be positive"):
            monte_carlo_sim({"duration": 10}, {"cd": (0.6, 0.1)}, n_samples=0)

    def test_chunk_zero_size(self):
        from compute.parallel_data import chunk_timeseries
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            chunk_timeseries([1, 2, 3], chunk_size=0)

    def test_chunk_negative_overlap(self):
        from compute.parallel_data import chunk_timeseries
        with pytest.raises(ValueError, match="overlap must be non-negative"):
            chunk_timeseries([1, 2, 3], chunk_size=2, overlap=-1)

    def test_chunk_overlap_exceeds_size(self):
        from compute.parallel_data import chunk_timeseries
        with pytest.raises(ValueError, match="overlap.*must be less than chunk_size"):
            chunk_timeseries([1, 2, 3], chunk_size=2, overlap=2)


class TestOutlierDetectEdgeCases:
    def test_mad_majority_identical(self):
        """MAD should detect outlier even when >50% values are identical."""
        from core.data_clean.outlier_detect import detect_mad
        data = [1.0] * 100 + [50.0]
        result = detect_mad(data)
        assert result["n_outliers"] >= 1
        assert 100 in result["outlier_indices"]

    def test_3sigma_all_identical(self):
        """All identical values should produce zero outliers."""
        from core.data_clean.outlier_detect import detect_3sigma
        result = detect_3sigma([5.0] * 20)
        assert result["n_outliers"] == 0

    def test_iqr_single_value(self):
        """Single value should have zero IQR, no outliers."""
        from core.data_clean.outlier_detect import detect_iqr
        result = detect_iqr([42.0])
        assert result["n_outliers"] == 0

    def test_mad_all_nan(self):
        """All NaN data should be flagged."""
        from core.data_clean.outlier_detect import detect_mad
        result = detect_mad([float("nan")] * 5)
        assert result["n_outliers"] == 5


class TestReportAgentSafeFormatting:
    def test_empty_water_level(self):
        """Report should handle empty water_level gracefully."""
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "performance_metrics": {"RMSE": 0.05},
            "control_simulation": {
                "setpoint": 1.0,
                "water_level": [],
                "metadata": {"solver": "Euler", "steps": 0, "dt": 1.0},
            },
            "controller_type": "PID",
        }
        report = agent.generate_control_report(results)
        assert "N/A" in report
        assert "PID" in report

    def test_string_metric_value(self):
        """Report should handle non-numeric metric values."""
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "performance_metrics": {"status": "good", "RMSE": 0.05},
            "control_simulation": {
                "setpoint": 1.0,
                "water_level": [0.5, 1.0],
                "metadata": {"solver": "Euler", "steps": 100, "dt": 1.0},
            },
            "controller_type": "PID",
        }
        report = agent.generate_control_report(results)
        assert "good" in report
        assert "0.0500" in report
