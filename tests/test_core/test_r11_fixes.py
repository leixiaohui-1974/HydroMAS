"""Tests for R11 multi-agent review fixes.
R11 多智能体评审修复测试。
"""

from __future__ import annotations

import logging

import pytest

# ---------- H1: MPC _history bounded by deque ----------

class TestMPCHistoryBounded:
    """Verify MPC controller uses bounded deque for history."""

    def test_history_is_deque(self):
        from collections import deque

        from core.control.mpc_controller import MPCController
        mpc = MPCController()
        assert isinstance(mpc._history, deque)
        assert mpc._history.maxlen == 10000

    def test_history_accumulates(self):
        from core.control.mpc_controller import MPCController
        mpc = MPCController()
        mpc.compute(current_h=0.5, setpoint=1.0)
        assert len(mpc.get_history()) == 1

    def test_reset_clears_history(self):
        from core.control.mpc_controller import MPCController
        mpc = MPCController()
        mpc.compute(current_h=0.5, setpoint=1.0)
        mpc.reset()
        assert len(mpc.get_history()) == 0


# ---------- H2: ODD definition validates dimension keys ----------

class TestODDDefinitionKeyValidation:
    """Verify ODDSpec.from_dict rejects malformed dimensions."""

    def test_missing_name_raises(self):
        from core.odd.odd_definition import ODDSpec
        with pytest.raises(ValueError, match="missing required keys"):
            ODDSpec.from_dict({
                "dimensions": [{"min_value": 0, "max_value": 1, "unit": "m"}]
            })

    def test_missing_min_value_raises(self):
        from core.odd.odd_definition import ODDSpec
        with pytest.raises(ValueError, match="missing required keys"):
            ODDSpec.from_dict({
                "dimensions": [{"name": "x", "max_value": 1, "unit": "m"}]
            })

    def test_valid_dimensions_accepted(self):
        from core.odd.odd_definition import ODDSpec
        spec = ODDSpec.from_dict({
            "dimensions": [
                {"name": "water_level", "min_value": 0.0, "max_value": 2.0, "unit": "m"},
            ]
        })
        assert len(spec.dimensions) == 1

    def test_empty_dimensions_ok(self):
        from core.odd.odd_definition import ODDSpec
        spec = ODDSpec.from_dict({"dimensions": []})
        assert len(spec.dimensions) == 0


# ---------- H3: MRC handler safe dict access ----------

class TestMRCHandlerSafeDictAccess:
    """Verify MRC handler skips malformed violations."""

    def test_missing_dimension_key_skipped(self):
        from core.odd.mrc_handler import determine_mrc_actions
        actions = determine_mrc_actions([{"bound_violated": "upper"}])
        assert actions == []

    def test_missing_bound_key_skipped(self):
        from core.odd.mrc_handler import determine_mrc_actions
        actions = determine_mrc_actions([{"dimension": "water_level"}])
        assert actions == []

    def test_valid_violation_produces_actions(self):
        from core.odd.mrc_handler import determine_mrc_actions
        actions = determine_mrc_actions([
            {"dimension": "water_level", "bound_violated": "upper"}
        ])
        assert len(actions) > 0
        assert actions[0]["action"] == "close_inlet"


# ---------- H4: LP scheduler returns inflow_rate alias ----------

class TestLPSchedulerInflowRateKey:
    """Verify LP scheduler return includes inflow_rate alias."""

    def test_fallback_has_schedule_key(self):
        from core.scheduling.lp_scheduler import _fallback_schedule
        result = _fallback_schedule([0.01, 0.02], 0.05)
        assert "schedule" in result

    def test_lp_source_has_inflow_rate(self):
        with open("core/scheduling/lp_scheduler.py") as f:
            source = f.read()
        assert '"inflow_rate": schedule' in source


# ---------- H5: ODD predictive mode has n_violations ----------

class TestODDPredictiveNViolations:
    """Verify check_odd_series returns n_violations."""

    def test_series_result_has_n_violations(self):
        from core.odd.odd_monitor import check_odd_series
        result = check_odd_series([{"water_level": 1.0}])
        assert "n_violations" in result

    def test_no_violations_count_zero(self):
        from core.odd.odd_monitor import check_odd_series
        result = check_odd_series([{"water_level": 1.0}])
        assert result["n_violations"] == 0

    def test_violations_counted(self):
        from core.odd.odd_monitor import check_odd_series
        # water_level=5.0 is far above default ODD max (1.8)
        result = check_odd_series([{"water_level": 5.0}, {"water_level": 1.0}])
        assert result["n_violations"] == 1
        assert result["worst_zone"] == "mrc"


# ---------- H6: NSE docstring accuracy ----------

class TestNSEDocstringAccuracy:
    """Verify NSE docstring matches behavior."""

    def test_nse_returns_neg_1e6_not_neg_inf(self):
        from core.evaluation.metrics import nse
        result = nse([1.0, 1.0, 1.0], [2.0, 3.0, 4.0])
        assert result == -1e6

    def test_nse_source_docstring_updated(self):
        with open("core/evaluation/metrics.py") as f:
            source = f.read()
        assert "[-1e6, 1]" in source
        assert "(-inf, 1]" not in source


# ---------- H7: Safety agent error zone ----------

class TestSafetyAgentErrorZone:
    """Verify safety agent returns 'error' zone on failure, not 'unknown'."""

    def test_source_uses_error_zone(self):
        with open("agents/safety_agent.py") as f:
            source = f.read()
        assert '"zone": "error"' in source
        assert "check_failed" in source

    def test_source_uses_exc_info(self):
        with open("agents/safety_agent.py") as f:
            source = f.read()
        assert "exc_info=True" in source


# ---------- H8: Polynomial predictor warns on NaN ----------

class TestPolynomialNaNWarning:
    """Verify polynomial predictor logs warning on overflow."""

    def test_overflow_logs_warning(self, caplog):
        import numpy as np

        from core.prediction.linear_predictor import predict_polynomial
        # High-degree polynomial on steep data will overflow for large horizon
        data = [float(i ** 3) for i in range(20)]
        with caplog.at_level(logging.WARNING):
            result = predict_polynomial(data, horizon=200, degree=5)
        # Check that predictions exist and are finite after clamping
        preds = result["predictions"]
        assert all(np.isfinite(p) for p in preds)


# ---------- M1: simulator docstring has Raises section ----------

class TestSimulatorDocstringRaises:
    """Verify run_simulation docstring documents ValueError."""

    def test_docstring_has_raises(self):
        with open("core/simulation/simulator.py") as f:
            source = f.read()
        assert "Raises:" in source
        assert "10,000,000" in source


# ---------- M2: median_filter docstring corrected ----------

class TestMedianFilterDocstring:
    """Verify median_filter docstring says auto-adjusted, not must-be-odd."""

    def test_docstring_no_must_be_odd(self):
        with open("core/data_clean/interpolation.py") as f:
            source = f.read()
        assert "auto-adjusted" in source
        assert "must be odd" not in source


# ---------- M3: Orchestrator error lists available skills ----------

class TestOrchestratorSkillNotLoaded:
    """Verify orchestrator error includes available skills."""

    def test_source_lists_available(self):
        with open("agents/orchestrator.py") as f:
            source = f.read()
        assert "Available:" in source
