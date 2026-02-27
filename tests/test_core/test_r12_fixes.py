"""Tests for R12 multi-agent review fixes.
R12 多智能体评审修复测试 — boundary values, NaN validation, import hygiene.
"""

from __future__ import annotations

import math

import pytest

# ---------- H1: classify_value NaN → "mrc" (safety) ----------

class TestClassifyValueNaN:
    """NaN and inf must be classified as 'mrc' for safety."""

    def test_nan_classified_as_mrc(self):
        from core.odd.odd_definition import DimensionSpec
        from core.odd.odd_monitor import classify_value
        dim = DimensionSpec(
            name="water_level", min_value=0.0, max_value=2.0,
            unit="m", warning_margin=0.1,
        )
        assert classify_value(float("nan"), dim) == "mrc"

    def test_positive_inf_classified_as_mrc(self):
        from core.odd.odd_definition import DimensionSpec
        from core.odd.odd_monitor import classify_value
        dim = DimensionSpec(
            name="water_level", min_value=0.0, max_value=2.0,
            unit="m", warning_margin=0.1,
        )
        assert classify_value(float("inf"), dim) == "mrc"

    def test_negative_inf_classified_as_mrc(self):
        from core.odd.odd_definition import DimensionSpec
        from core.odd.odd_monitor import classify_value
        dim = DimensionSpec(
            name="water_level", min_value=0.0, max_value=2.0,
            unit="m", warning_margin=0.1,
        )
        assert classify_value(float("-inf"), dim) == "mrc"

    def test_normal_value_still_normal(self):
        from core.odd.odd_definition import DimensionSpec
        from core.odd.odd_monitor import classify_value
        dim = DimensionSpec(
            name="water_level", min_value=0.0, max_value=2.0,
            unit="m", warning_margin=0.1,
        )
        assert classify_value(1.0, dim) == "normal"


# ---------- H2: PID NaN/inf validation ----------

class TestPIDNaNValidation:
    """PID controller must reject NaN/inf inputs."""

    def test_nan_setpoint_raises(self):
        from core.control.pid_controller import PIDController
        pid = PIDController()
        with pytest.raises(ValueError, match="finite"):
            pid.compute(setpoint=float("nan"), measured=1.0)

    def test_inf_measured_raises(self):
        from core.control.pid_controller import PIDController
        pid = PIDController()
        with pytest.raises(ValueError, match="finite"):
            pid.compute(setpoint=1.0, measured=float("inf"))

    def test_finite_values_work(self):
        from core.control.pid_controller import PIDController
        pid = PIDController()
        result = pid.compute(setpoint=1.0, measured=0.5)
        assert math.isfinite(result)


# ---------- H3: MPC NaN validation ----------

class TestMPCNaNValidation:
    """MPC controller must reject NaN/inf inputs."""

    def test_nan_current_h_raises(self):
        from core.control.mpc_controller import MPCController
        mpc = MPCController()
        with pytest.raises(ValueError, match="finite"):
            mpc.compute(current_h=float("nan"), setpoint=1.0)

    def test_inf_setpoint_raises(self):
        from core.control.mpc_controller import MPCController
        mpc = MPCController()
        with pytest.raises(ValueError, match="finite"):
            mpc.compute(current_h=0.5, setpoint=float("inf"))

    def test_finite_values_work(self):
        from core.control.mpc_controller import MPCController
        mpc = MPCController()
        result = mpc.compute(current_h=0.5, setpoint=1.0)
        assert math.isfinite(result)


# ---------- H4: predict_linear NaN validation ----------

class TestPredictLinearNaN:
    """predict_linear must reject NaN/inf in historical data."""

    def test_nan_in_data_raises(self):
        from core.prediction.linear_predictor import predict_linear
        with pytest.raises(ValueError, match="NaN or inf"):
            predict_linear([1.0, float("nan"), 3.0])

    def test_inf_in_data_raises(self):
        from core.prediction.linear_predictor import predict_linear
        with pytest.raises(ValueError, match="NaN or inf"):
            predict_linear([1.0, float("inf"), 3.0])

    def test_clean_data_works(self):
        from core.prediction.linear_predictor import predict_linear
        result = predict_linear([1.0, 2.0, 3.0, 4.0], horizon=5)
        assert len(result["predictions"]) == 5


# ---------- H5: LP scheduler negative demand validation ----------

class TestLPNegativeDemand:
    """LP scheduler must reject negative demand values."""

    def test_negative_demand_raises(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        with pytest.raises(ValueError, match="non-negative"):
            optimize_schedule_lp([-0.01, 0.02], supply_capacity=0.05)

    def test_zero_demand_allowed(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        result = optimize_schedule_lp([0.0, 0.0, 0.0], supply_capacity=0.05)
        assert result["status"] in ("optimal", "rule_based", "fallback")

    def test_positive_demand_works(self):
        from core.scheduling.lp_scheduler import optimize_schedule_lp
        result = optimize_schedule_lp([0.01, 0.02], supply_capacity=0.05)
        assert "schedule" in result


# ---------- H6: control_server NaN setpoint ----------

class TestControlServerNaN:
    """control_server must reject NaN/inf setpoint."""

    def test_nan_setpoint_raises(self):
        from mcp_servers.control_server import run_controller
        with pytest.raises(ValueError, match="finite"):
            run_controller(setpoint=float("nan"))

    def test_inf_setpoint_raises(self):
        from mcp_servers.control_server import run_controller
        with pytest.raises(ValueError, match="finite"):
            run_controller(setpoint=float("inf"))

    def test_normal_setpoint_works(self):
        from mcp_servers.control_server import run_controller
        result = run_controller(setpoint=1.0)
        assert "control_output" in result


# ---------- M1: LP fallback logs warning ----------

class TestLPFallbackLogging:
    """LP scheduler fallback should log when PuLP unavailable."""

    def test_source_has_warning_log(self):
        with open("core/scheduling/lp_scheduler.py") as f:
            source = f.read()
        assert "PuLP not available" in source
        assert ".warning(" in source


# ---------- M2: sensitivity_oat n_levels < 2 ----------

class TestSensitivityNLevels:
    """sensitivity_oat must require n_levels >= 2."""

    def test_n_levels_1_raises(self):
        from core.design.sensitivity import sensitivity_oat
        with pytest.raises(ValueError, match="at least 2"):
            sensitivity_oat(
                base_params={"x": 1.0},
                param_ranges={"x": (0.5, 1.5)},
                evaluate_fn=lambda p: p["x"],
                n_levels=1,
            )

    def test_n_levels_0_raises(self):
        from core.design.sensitivity import sensitivity_oat
        with pytest.raises(ValueError, match="at least 2"):
            sensitivity_oat(
                base_params={"x": 1.0},
                param_ranges={"x": (0.5, 1.5)},
                evaluate_fn=lambda p: p["x"],
                n_levels=0,
            )

    def test_n_levels_2_works(self):
        from core.design.sensitivity import sensitivity_oat
        result = sensitivity_oat(
            base_params={"x": 1.0},
            param_ranges={"x": (0.5, 1.5)},
            evaluate_fn=lambda p: p["x"],
            n_levels=2,
        )
        assert result["method"] == "OAT"


# ---------- M4: asyncio imports at top level ----------

class TestAsyncioImports:
    """asyncio should be imported at top-level, not lazily."""

    def test_orchestrator_asyncio_top_level(self):
        with open("agents/orchestrator.py") as f:
            lines = f.readlines()
        # asyncio should be in top imports (first 25 lines)
        top = "".join(lines[:25])
        assert "import asyncio" in top

    def test_base_skill_asyncio_top_level(self):
        with open("skills/base_skill.py") as f:
            lines = f.readlines()
        top = "".join(lines[:25])
        assert "import asyncio" in top
