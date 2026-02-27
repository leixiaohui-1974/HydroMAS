"""Tests for R10 multi-agent review fixes.
R10 多智能体评审修复测试。
"""

from __future__ import annotations

import logging
import threading

import pytest

# ---------- H-NS3: compute_outflow belt-and-suspenders sqrt safety ----------

class TestComputeOutflowSqrtSafety:
    """Verify compute_outflow safely handles edge-case h values."""

    def test_negative_h_returns_zero(self):
        from core.simulation.tank_model import TankParams, compute_outflow
        params = TankParams()
        assert compute_outflow(-0.01, params) == 0.0

    def test_zero_h_returns_zero(self):
        from core.simulation.tank_model import TankParams, compute_outflow
        params = TankParams()
        assert compute_outflow(0.0, params) == 0.0

    def test_positive_h_returns_positive(self):
        from core.simulation.tank_model import TankParams, compute_outflow
        params = TankParams()
        result = compute_outflow(1.0, params)
        assert result > 0.0

    def test_very_small_positive_h(self):
        from core.simulation.tank_model import TankParams, compute_outflow
        params = TankParams()
        result = compute_outflow(1e-15, params)
        assert result >= 0.0  # Must not be NaN


# ---------- H-NS2: run_simulation MAX_STEPS guard ----------

class TestSimulationMaxSteps:
    """Verify simulation rejects excessively fine time steps."""

    def test_reasonable_steps_work(self):
        from core.simulation.simulator import run_simulation
        result = run_simulation(duration=10, dt=1.0)
        assert "water_level" in result

    def test_excessive_steps_raises(self):
        from core.simulation.simulator import run_simulation
        with pytest.raises(ValueError, match="exceeding limit"):
            run_simulation(duration=1e10, dt=0.001)

    def test_boundary_steps_work(self):
        from core.simulation.simulator import run_simulation
        # 10_000 steps — well within limit
        result = run_simulation(duration=10000, dt=1.0)
        assert len(result["water_level"]) == 10001


# ---------- H-API1: control_server validates "h" in current_state ----------

class TestControlServerStateValidation:
    """Verify control_server rejects missing 'h' key."""

    def test_missing_h_key_raises(self):
        from mcp_servers.control_server import run_controller
        with pytest.raises(ValueError, match="must contain key 'h'"):
            run_controller(
                setpoint=1.0,
                current_state={"water_level": 0.5},  # wrong key
                controller_type="PID",
            )

    def test_valid_state_works(self):
        from mcp_servers.control_server import run_controller
        result = run_controller(
            setpoint=1.0,
            current_state={"h": 0.5},
            controller_type="PID",
        )
        assert "control_output" in result

    def test_default_state_works(self):
        from mcp_servers.control_server import run_controller
        result = run_controller(setpoint=1.0, controller_type="PID")
        assert "control_output" in result


# ---------- H-API3: design_server validates param_ranges format ----------

class TestDesignServerParamRanges:
    """Verify run_sensitivity rejects malformed param_ranges."""

    def test_single_element_range_raises(self):
        from mcp_servers.design_server import run_sensitivity
        with pytest.raises(ValueError, match="param_ranges"):
            run_sensitivity(
                base_params={"area": 1.0},
                param_ranges={"area": [0.5]},  # needs [min, max]
            )

    def test_empty_range_raises(self):
        from mcp_servers.design_server import run_sensitivity
        with pytest.raises(ValueError, match="param_ranges"):
            run_sensitivity(
                base_params={"area": 1.0},
                param_ranges={"area": []},
            )

    def test_non_list_range_raises(self):
        from mcp_servers.design_server import run_sensitivity
        with pytest.raises(ValueError, match="param_ranges"):
            run_sensitivity(
                base_params={"area": 1.0},
                param_ranges={"area": 1.0},
            )

    def test_valid_range_accepted(self):
        from mcp_servers.design_server import run_sensitivity
        result = run_sensitivity(
            base_params={"area": 1.0},
            param_ranges={"area": [0.5, 2.0]},
            method="OAT",
            n_levels=3,
        )
        assert "parameters" in result


# ---------- H-CON1: thread-safe _resolved_tools ----------

class TestThreadSafeToolResolution:
    """Verify _resolved_tools uses a lock for thread safety."""

    def test_lock_exists(self):
        from skills.base_skill import _resolved_tools_lock
        assert isinstance(_resolved_tools_lock, type(threading.Lock()))

    def test_concurrent_tool_resolution(self):
        """Multiple threads resolving tools concurrently should not corrupt state."""
        from skills.base_skill import _call_tool_dynamic

        results = []
        errors = []

        def resolve_tool():
            try:
                result = _call_tool_dynamic("simulate_tank", {
                    "duration": 10, "dt": 1.0,
                })
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=resolve_tool) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent resolution errors: {errors}"
        assert len(results) == 5
        for r in results:
            assert "water_level" in r


# ---------- H-LC1: unknown metric warning ----------

class TestUnknownMetricWarning:
    """Verify evaluate_performance warns on unknown metrics."""

    def test_unknown_metric_logs_warning(self, caplog):
        from core.evaluation.metrics import evaluate_performance
        with caplog.at_level(logging.WARNING, logger="core.evaluation.metrics"):
            result = evaluate_performance(
                [1.0, 2.0], [1.1, 2.1],
                metrics_list=["RMSE", "BOGUS_METRIC"],
            )
        assert "RMSE" in result
        assert "BOGUS_METRIC" not in result
        assert any("Unknown metric" in r.message for r in caplog.records)

    def test_known_metrics_no_warning(self, caplog):
        from core.evaluation.metrics import evaluate_performance
        with caplog.at_level(logging.WARNING, logger="core.evaluation.metrics"):
            result = evaluate_performance(
                [1.0, 2.0], [1.1, 2.1],
                metrics_list=["RMSE", "MAE", "NSE"],
            )
        assert len(result) == 3
        assert not any("Unknown metric" in r.message for r in caplog.records)

    def test_control_metrics_without_prereqs_no_warning(self, caplog):
        """Control metrics that are known but missing prereqs should not warn."""
        from core.evaluation.metrics import evaluate_performance
        with caplog.at_level(logging.WARNING, logger="core.evaluation.metrics"):
            result = evaluate_performance(
                [1.0, 2.0], [1.1, 2.1],
                metrics_list=["SETTLING_TIME"],  # known but needs time_series+setpoint
            )
        assert "SETTLING_TIME" not in result  # skipped due to missing prereqs
        assert not any("Unknown metric" in r.message for r in caplog.records)
