"""Tests for R13 multi-agent review fixes.
R13 多智能体评审修复测试 — defensive copies, float comparison, state leakage, regressions.
"""

from __future__ import annotations

import math

import pytest

# ---------- H1: lru_cache returns deep copies (no cache poisoning) ----------

class TestConfigDeepCopy:
    """Callers mutating returned config must NOT corrupt the cache."""

    def test_load_tank_config_returns_independent_copies(self):
        from core.config import load_tank_config
        c1 = load_tank_config()
        c1["tank_params"]["area"] = 999.0
        c2 = load_tank_config()
        assert c2["tank_params"]["area"] != 999.0

    def test_load_odd_specs_returns_independent_copies(self):
        from core.config import load_odd_specs
        s1 = load_odd_specs()
        s1["dimensions"][0]["name"] = "MUTATED"
        s2 = load_odd_specs()
        assert s2["dimensions"][0]["name"] != "MUTATED"

    def test_load_sample_timeseries_returns_independent_copies(self):
        from core.config import load_sample_timeseries
        t1 = load_sample_timeseries()
        original_first = t1["time"][0]
        t1["time"][0] = -999.0
        t2 = load_sample_timeseries()
        assert t2["time"][0] == original_first


# ---------- H2: PID anti-windup uses isclose ----------

class TestPIDAntiWindupIsclose:
    """PID anti-windup should use math.isclose instead of !=."""

    def test_source_uses_isclose(self):
        with open("core/control/pid_controller.py") as f:
            source = f.read()
        assert "math.isclose(clamped, output)" in source
        assert "clamped != output" not in source

    def test_anti_windup_still_works(self):
        from core.control.pid_controller import PIDController, PIDParams
        pid = PIDController(PIDParams(kp=10.0, ki=5.0, output_max=0.05))
        # Drive with large error to saturate
        for _ in range(10):
            pid.compute(setpoint=2.0, measured=0.0, dt=1.0)
        # After saturation, integral should be bounded
        hist = pid.get_history()
        assert all(h["output"] <= 0.05 for h in hist)


# ---------- H3: NSE uses np.isclose for zero checks ----------

class TestNSEIsclose:
    """NSE should use np.isclose for ss_tot and ss_res checks."""

    def test_source_uses_isclose(self):
        with open("core/evaluation/metrics.py") as f:
            source = f.read()
        assert "np.isclose(ss_tot" in source
        assert "np.isclose(ss_res" in source

    def test_nse_constant_observed_exact_match(self):
        from core.evaluation.metrics import nse
        result = nse([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
        assert result == 1.0

    def test_nse_constant_observed_mismatch(self):
        from core.evaluation.metrics import nse
        result = nse([1.0, 1.0, 1.0], [2.0, 3.0, 4.0])
        assert result == -1e6


# ---------- H4: sensitivity uses np.isclose ----------

class TestSensitivityIsclose:
    """sensitivity_oat should use np.isclose for float comparisons."""

    def test_source_uses_isclose(self):
        with open("core/design/sensitivity.py") as f:
            source = f.read()
        assert "np.isclose(base_output" in source
        assert "np.isclose(param_range" in source

    def test_sensitivity_near_zero_baseline(self):
        from core.design.sensitivity import sensitivity_oat
        # base_output is nearly zero — should not divide by it
        result = sensitivity_oat(
            base_params={"x": 0.0},
            param_ranges={"x": (0.0, 1.0)},
            evaluate_fn=lambda p: p["x"] * 1e-20,  # near-zero output
            n_levels=3,
        )
        si = result["parameters"]["x"]["sensitivity_index"]
        assert math.isfinite(si)


# ---------- H5: ODD spec duplicate name check (regression fix) ----------

class TestODDDuplicateNames:
    """ODDSpec.add_dimension should reject duplicate names."""

    def test_duplicate_name_raises(self):
        from core.odd.odd_definition import ODDSpec
        spec = ODDSpec()
        spec.add_dimension("water_level", 0.0, 2.0, "m")
        with pytest.raises(ValueError, match="Duplicate"):
            spec.add_dimension("water_level", 0.0, 3.0, "m")

    def test_unique_names_ok(self):
        from core.odd.odd_definition import ODDSpec
        spec = ODDSpec()
        spec.add_dimension("water_level", 0.0, 2.0, "m")
        spec.add_dimension("temperature", 0.0, 40.0, "°C")
        assert len(spec.dimensions) == 2


# ---------- M1: outlier detect std uses np.isclose ----------

class TestOutlierStdIsclose:
    """detect_3sigma should use np.isclose(std, 0)."""

    def test_source_uses_isclose(self):
        with open("core/data_clean/outlier_detect.py") as f:
            source = f.read()
        assert "np.isclose(std, 0.0)" in source

    def test_constant_data_no_outliers(self):
        from core.data_clean.outlier_detect import detect_3sigma
        result = detect_3sigma([5.0] * 100)
        assert result["n_outliers"] == 0


# ---------- M2: outlier detect MAD uses np.isclose ----------

class TestOutlierMADIsclose:
    """detect_mad should use np.isclose(mad, 0)."""

    def test_source_uses_isclose(self):
        with open("core/data_clean/outlier_detect.py") as f:
            source = f.read()
        assert "np.isclose(mad, 0.0)" in source

    def test_constant_data_no_outliers(self):
        from core.data_clean.outlier_detect import detect_mad
        result = detect_mad([3.0] * 50)
        assert result["n_outliers"] == 0


# ---------- M3: ARX R² uses np.isclose ----------

class TestARXRSquaredIsclose:
    """ARX R² computation should use np.isclose."""

    def test_source_uses_isclose(self):
        with open("core/identification/arx_model.py") as f:
            source = f.read()
        assert "np.isclose(ss_tot" in source


# ---------- M4: least_squares R² uses np.isclose ----------

class TestLeastSquaresRSquaredIsclose:
    """Least squares R² should use np.isclose."""

    def test_source_uses_isclose(self):
        with open("core/identification/least_squares.py") as f:
            source = f.read()
        assert "np.isclose(ss_tot" in source


# ---------- M5: settling_time uses np.isclose ----------

class TestSettlingTimeIsclose:
    """settling_time should use np.isclose for setpoint check."""

    def test_source_uses_isclose(self):
        with open("core/evaluation/metrics.py") as f:
            source = f.read()
        # settling_time band calculation
        assert "np.isclose(setpoint, 0.0)" in source

    def test_settling_near_zero_setpoint(self):
        from core.evaluation.metrics import settling_time
        # Near-zero setpoint should use tolerance as band, not setpoint*tolerance
        result = settling_time(
            time_series=[0.0, 1.0, 2.0, 3.0],
            value_series=[0.01, 0.005, 0.001, 0.0001],
            setpoint=0.0,
            tolerance=0.02,
        )
        # All values within tolerance=0.02 of setpoint=0.0
        assert result == 0.0
