"""Tests for R8 multi-agent review fixes.
R8 多智能体评审修复测试。
"""

from __future__ import annotations

import math

import numpy as np
import pytest


# ---------- H1: overshoot near-zero setpoint ----------

class TestOvershootNearZeroSetpoint:
    """Verify overshoot handles near-zero setpoints safely."""

    def test_exactly_zero_setpoint(self):
        from core.evaluation.metrics import overshoot
        result = overshoot([0.1, 0.2, 0.3], 0.0)
        assert result == 0.0

    def test_near_zero_setpoint(self):
        from core.evaluation.metrics import overshoot
        result = overshoot([0.1, 0.2, 0.3], 1e-15)
        assert result == 0.0  # should not explode

    def test_normal_setpoint(self):
        from core.evaluation.metrics import overshoot
        result = overshoot([0.5, 1.2, 1.0], 1.0)
        assert result == pytest.approx(20.0)


# ---------- H2: NSE finite return for constant observed ----------

class TestNSEFiniteReturn:
    """Verify NSE returns finite value when ss_tot=0."""

    def test_constant_obs_perfect_pred(self):
        from core.evaluation.metrics import nse
        result = nse([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
        assert result == 1.0

    def test_constant_obs_different_pred(self):
        from core.evaluation.metrics import nse
        result = nse([1.0, 1.0, 1.0], [2.0, 2.0, 2.0])
        assert result == -1e6
        assert math.isfinite(result)  # must be finite, not -inf


# ---------- H3: config loading outside loop ----------

class TestConfigOutsideLoop:
    """Verify load_tank_config is called outside ranking loop."""

    def test_no_load_in_loop(self):
        with open("skills/rehearsal_skill.py") as f:
            source = f.read()
        # The import + call should appear before the for loop, not inside
        lines = source.split("\n")
        load_line = None
        for_line = None
        for i, line in enumerate(lines):
            if "load_tank_config" in line and "from core.config" in line:
                load_line = i
            if "for i, ev in enumerate" in line:
                for_line = i
                break
        assert load_line is not None
        assert for_line is not None
        assert load_line < for_line, "load_tank_config should be called before the loop"


# ---------- H4: sensitivity_oat all-NaN handling ----------

class TestSensitivityAllNaN:
    """Verify OAT handles all-NaN outputs gracefully."""

    def test_all_nan_returns_marker(self):
        from core.design.sensitivity import sensitivity_oat

        def always_nan(params):
            return float("nan")

        result = sensitivity_oat(
            base_params={"x": 1.0},
            param_ranges={"x": (0.0, 2.0)},
            evaluate_fn=always_nan,
            n_levels=5,
        )
        param_result = result["parameters"]["x"]
        assert param_result["all_nan"] is True
        assert param_result["sensitivity_index"] == 0.0

    def test_partial_nan_still_works(self):
        from core.design.sensitivity import sensitivity_oat

        call_count = [0]

        def sometimes_nan(params):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                return float("nan")
            return params["x"] * 2

        result = sensitivity_oat(
            base_params={"x": 1.0},
            param_ranges={"x": (0.0, 2.0)},
            evaluate_fn=sometimes_nan,
            n_levels=5,
        )
        param_result = result["parameters"]["x"]
        assert "all_nan" not in param_result
        assert param_result["sensitivity_index"] > 0


# ---------- H6: median_filter window_size validation ----------

class TestMedianFilterWindowValidation:
    """Verify median_filter rejects non-positive window_size."""

    def test_zero_window_raises(self):
        from core.data_clean.interpolation import median_filter
        with pytest.raises(ValueError, match="positive"):
            median_filter([1.0, 2.0, 3.0], window_size=0)

    def test_negative_window_raises(self):
        from core.data_clean.interpolation import median_filter
        with pytest.raises(ValueError, match="positive"):
            median_filter([1.0, 2.0, 3.0], window_size=-3)

    def test_valid_window_works(self):
        from core.data_clean.interpolation import median_filter
        result = median_filter([1.0, 2.0, 3.0], window_size=3)
        assert len(result["data"]) == 3


# ---------- M1: Morris empty params and validation ----------

class TestMorrisValidation:
    """Verify Morris sensitivity handles edge cases."""

    def test_n_levels_1_raises(self):
        from core.design.sensitivity import sensitivity_morris
        with pytest.raises(ValueError, match="at least 2"):
            sensitivity_morris(
                param_ranges={"x": (0, 1)},
                evaluate_fn=lambda p: p["x"],
                n_levels=1,
            )

    def test_empty_params_raises(self):
        from core.design.sensitivity import sensitivity_morris
        with pytest.raises(ValueError, match="empty"):
            sensitivity_morris(
                param_ranges={},
                evaluate_fn=lambda p: 1.0,
            )


# ---------- M2: DataAnalysisPredict backtest slice bounds ----------

class TestBacktestSliceBounds:
    """Verify backtest slice is clamped to cleaned_data length."""

    def test_slice_bounds_in_source(self):
        with open("skills/data_analysis_predict.py") as f:
            source = f.read()
        assert "min(len(predict_result" in source


# ---------- M3: settling_time boundary safety ----------

class TestSettlingTimeBoundary:
    """Verify settling_time handles boundary conditions."""

    def test_last_sample_outside(self):
        from core.evaluation.metrics import settling_time
        # Last sample is outside band => never settled
        result = settling_time(
            [0, 1, 2, 3, 4],
            [1.0, 1.0, 1.0, 1.0, 2.0],  # last point outside
            setpoint=1.0,
            tolerance=0.02,
        )
        assert result is None

    def test_settles_at_second_to_last(self):
        from core.evaluation.metrics import settling_time
        result = settling_time(
            [0, 1, 2, 3, 4],
            [2.0, 1.5, 1.0, 1.0, 1.0],  # settles at index 2
            setpoint=1.0,
            tolerance=0.5,  # wide band
        )
        assert result is not None


# ---------- M4: polynomial overflow sanitization ----------

class TestPolynomialOverflow:
    """Verify polynomial predictions are sanitized for overflow."""

    def test_high_degree_large_horizon(self):
        from core.prediction.linear_predictor import predict_polynomial
        # High degree + large horizon should produce finite results
        data = [float(i) for i in range(20)]
        result = predict_polynomial(data, horizon=10000, degree=5)
        preds = result["predictions"]
        assert all(math.isfinite(p) for p in preds)

    def test_normal_prediction_unchanged(self):
        from core.prediction.linear_predictor import predict_polynomial
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = predict_polynomial(data, horizon=5, degree=1)
        # Linear predictions should be finite and reasonable
        assert all(math.isfinite(p) for p in result["predictions"])
