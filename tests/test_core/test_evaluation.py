"""Tests for core.evaluation module."""

import pytest

from core.evaluation.metrics import (
    evaluate_performance,
    mae,
    mape,
    nse,
    overshoot,
    rmse,
    settling_time,
    steady_state_error,
)
from core.evaluation.wnal_assessor import assess_wnal


class TestMetrics:
    def test_rmse_perfect(self):
        obs = [1.0, 2.0, 3.0]
        pred = [1.0, 2.0, 3.0]
        assert rmse(obs, pred) == 0.0

    def test_rmse_known(self):
        obs = [1.0, 2.0, 3.0]
        pred = [1.1, 2.1, 3.1]
        assert abs(rmse(obs, pred) - 0.1) < 1e-10

    def test_mae_perfect(self):
        assert mae([1, 2, 3], [1, 2, 3]) == 0.0

    def test_nse_perfect(self):
        assert nse([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0

    def test_nse_mean_predictor(self):
        """NSE = 0 when predictions equal the mean."""
        obs = [1.0, 2.0, 3.0, 4.0]
        mean_pred = [2.5] * 4
        assert abs(nse(obs, mean_pred)) < 1e-10

    def test_mape(self):
        obs = [100.0, 200.0]
        pred = [110.0, 180.0]
        assert abs(mape(obs, pred) - 10.0) < 1e-10

    def test_settling_time_immediate(self):
        t = [0, 1, 2, 3, 4]
        v = [1.0, 1.0, 1.0, 1.0, 1.0]
        assert settling_time(t, v, setpoint=1.0) == 0.0

    def test_settling_time_not_settled(self):
        t = [0, 1, 2, 3, 4]
        v = [0.0, 0.5, 0.8, 0.6, 0.4]
        result = settling_time(t, v, setpoint=1.0)
        assert result is None  # never settled

    def test_overshoot_none(self):
        assert overshoot([0.5, 0.8, 0.95, 1.0], setpoint=1.0) == 0.0

    def test_overshoot_present(self):
        assert overshoot([0.5, 1.0, 1.2, 1.0], setpoint=1.0) == pytest.approx(20.0)

    def test_steady_state_error(self):
        v = [0.5, 0.8, 0.95, 0.98, 0.99, 1.01, 1.0, 1.0, 1.0, 1.0]
        err = steady_state_error(v, setpoint=1.0, n_tail=5)
        assert abs(err) < 0.02


class TestEvaluatePerformance:
    def test_default_metrics(self):
        obs = [1.0, 2.0, 3.0]
        pred = [1.1, 2.0, 2.9]
        result = evaluate_performance(obs, pred)
        assert "RMSE" in result
        assert "MAE" in result
        assert "NSE" in result

    def test_control_metrics(self):
        t = list(range(20))
        v = [0.5 + 0.05 * i for i in range(20)]
        result = evaluate_performance(
            [1.0] * 20, v,
            metrics_list=["RMSE", "overshoot", "settling_time"],
            time_series=t,
            setpoint=1.0,
        )
        assert "RMSE" in result
        assert "OVERSHOOT" in result


class TestWNALAssessor:
    def test_low_level(self):
        caps = {
            k: 10.0
            for k in [
                "sensing", "communication", "modeling",
                "prediction", "control", "odd_monitoring",
                "decision_support",
            ]
        }
        result = assess_wnal(caps)
        assert result["level"] in ("L0", "L1")

    def test_high_level(self):
        caps = {
            k: 90.0
            for k in [
                "sensing", "communication", "modeling",
                "prediction", "control", "odd_monitoring",
                "decision_support",
            ]
        }
        result = assess_wnal(caps)
        assert result["level"] in ("L4", "L5")

    def test_gaps_reported(self):
        caps = {"sensing": 80, "control": 30}
        result = assess_wnal(caps)
        assert len(result["gaps"]) > 0

    def test_recommendations(self):
        caps = {"sensing": 50, "control": 50}
        result = assess_wnal(caps)
        assert len(result["recommendations"]) > 0
