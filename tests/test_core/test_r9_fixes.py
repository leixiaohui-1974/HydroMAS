"""Tests for R9 multi-agent review fixes.
R9 多智能体评审修复测试。
"""

from __future__ import annotations

import pytest

# ---------- H1: plan_skill empty water_level guard ----------

class TestPlanSkillEmptyWaterLevel:
    """Verify plan_skill handles empty water_level safely."""

    def test_empty_water_level_fallback(self):
        """Source uses `or [0.0]` to guard empty water_level."""
        with open("skills/plan_skill.py") as f:
            source = f.read()
        assert "or [0.0]" in source
        assert "or [0.5]" in source  # ODD check fallback

    def test_demand_sampling_bounds_clamped(self):
        """demand[min(i*step_size, len(demand)-1)] prevents IndexError."""
        with open("skills/plan_skill.py") as f:
            source = f.read()
        assert "min(i * step_size, len(demand) - 1)" in source


# ---------- H2: analysis_agent empty water_level guard ----------

class TestAnalysisAgentEmptyLevels:
    """Verify analysis_agent guards empty water_level."""

    def test_empty_guard_in_source(self):
        with open("agents/analysis_agent.py") as f:
            source = f.read()
        assert 'sim.get("water_level") or [0.0]' in source


# ---------- H3: odd_assessment empty water_level guard ----------

class TestODDAssessmentEmptyLevels:
    """Verify odd_assessment guards empty water_level."""

    def test_empty_guard_in_source(self):
        with open("skills/odd_assessment.py") as f:
            source = f.read()
        assert "if water_levels" in source
        assert 'sim.get("water_level") or []' in source


# ---------- H4: full_lifecycle array bounds ----------

class TestFullLifecycleArrayBounds:
    """Verify full_lifecycle guards control_output length."""

    def test_safe_array_access(self):
        with open("skills/full_lifecycle.py") as f:
            source = f.read()
        assert 'ctrl_result.get("water_level") or' in source
        assert 'ctrl_result.get("control_output") or' in source


# ---------- H5: config.py safe key access ----------

class TestConfigSafeKeyAccess:
    """Verify config functions use .get() with defaults."""

    def test_get_default_tank_params_uses_get(self):
        with open("core/config.py") as f:
            source = f.read()
        assert 'config.get("tank_params", {})' in source
        assert 'config.get("control_defaults", {}).get("pid", {})' in source
        assert 'config.get("control_defaults", {}).get("mpc", {})' in source
        assert 'config.get("simulation_defaults", {})' in source

    def test_functions_still_work(self):
        from core.config import (
            get_default_mpc_params,
            get_default_pid_params,
            get_default_simulation_params,
            get_default_tank_params,
        )
        tp = get_default_tank_params()
        assert "area" in tp
        pp = get_default_pid_params()
        assert "kp" in pp
        mp = get_default_mpc_params()
        assert "horizon" in mp
        sp = get_default_simulation_params()
        assert "duration" in sp


# ---------- H6: evaluation_server keyword args ----------

class TestEvaluationServerKeywordArgs:
    """Verify evaluation_server uses keyword args."""

    def test_keyword_args_in_source(self):
        with open("mcp_servers/evaluation_server.py") as f:
            source = f.read()
        assert "metrics_list=metrics" in source
        assert "time_series=time_series" in source
        assert "setpoint=setpoint" in source

    def test_evaluate_still_works(self):
        from mcp_servers.evaluation_server import evaluate_performance
        result = evaluate_performance(
            observed=[1.0, 2.0, 3.0],
            predicted=[1.1, 2.1, 2.9],
            metrics=["RMSE", "MAE"],
        )
        assert "RMSE" in result
        assert "MAE" in result


# ---------- M3: simulation_server row validation ----------

class TestSimulationServerRowValidation:
    """Verify simulation_server validates q_in_profile rows."""

    def test_valid_profile_works(self):
        from mcp_servers.simulation_server import simulate_tank
        result = simulate_tank(
            duration=10, dt=1.0,
            q_in_profile=[[0, 0.01], [10, 0.01]],
        )
        assert "water_level" in result

    def test_malformed_row_raises(self):
        from mcp_servers.simulation_server import simulate_tank
        with pytest.raises(ValueError, match="q_in_profile row"):
            simulate_tank(
                duration=10, dt=1.0,
                q_in_profile=[[0]],  # Missing value
            )

    def test_non_list_row_raises(self):
        from mcp_servers.simulation_server import simulate_tank
        with pytest.raises(ValueError, match="q_in_profile row"):
            simulate_tank(
                duration=10, dt=1.0,
                q_in_profile=["bad"],
            )


# ---------- M4: polynomial degree validation ----------

class TestPolynomialDegreeValidation:
    """Verify polynomial predictor rejects degree < 1."""

    def test_degree_zero_raises(self):
        from core.prediction.linear_predictor import predict_polynomial
        with pytest.raises(ValueError, match="degree must be >= 1"):
            predict_polynomial([1.0, 2.0, 3.0], degree=0)

    def test_negative_degree_raises(self):
        from core.prediction.linear_predictor import predict_polynomial
        with pytest.raises(ValueError, match="degree must be >= 1"):
            predict_polynomial([1.0, 2.0, 3.0], degree=-1)


# ---------- M5: Morris n_trajectories validation ----------

class TestMorrisNTrajectoriesValidation:
    """Verify Morris validates n_trajectories."""

    def test_zero_trajectories_raises(self):
        from core.design.sensitivity import sensitivity_morris
        with pytest.raises(ValueError, match="n_trajectories must be positive"):
            sensitivity_morris(
                param_ranges={"x": (0, 1)},
                evaluate_fn=lambda p: p["x"],
                n_trajectories=0,
            )

    def test_negative_trajectories_raises(self):
        from core.design.sensitivity import sensitivity_morris
        with pytest.raises(ValueError, match="n_trajectories must be positive"):
            sensitivity_morris(
                param_ranges={"x": (0, 1)},
                evaluate_fn=lambda p: p["x"],
                n_trajectories=-5,
            )


# ---------- M6: settling_time tolerance and n_tail validation ----------

class TestMetricsParameterValidation:
    """Verify metrics validate tolerance and n_tail."""

    def test_zero_tolerance_raises(self):
        from core.evaluation.metrics import settling_time
        with pytest.raises(ValueError, match="tolerance must be positive"):
            settling_time([0, 1, 2], [1.0, 1.0, 1.0], setpoint=1.0, tolerance=0)

    def test_negative_tolerance_raises(self):
        from core.evaluation.metrics import settling_time
        with pytest.raises(ValueError, match="tolerance must be positive"):
            settling_time([0, 1, 2], [1.0, 1.0, 1.0], setpoint=1.0, tolerance=-0.1)

    def test_zero_n_tail_raises(self):
        from core.evaluation.metrics import steady_state_error
        with pytest.raises(ValueError, match="n_tail must be positive"):
            steady_state_error([1.0, 1.0, 1.0], setpoint=1.0, n_tail=0)

    def test_negative_n_tail_raises(self):
        from core.evaluation.metrics import steady_state_error
        with pytest.raises(ValueError, match="n_tail must be positive"):
            steady_state_error([1.0, 1.0, 1.0], setpoint=1.0, n_tail=-1)

    def test_valid_tolerance_works(self):
        from core.evaluation.metrics import settling_time
        result = settling_time([0, 1, 2], [1.0, 1.0, 1.0], setpoint=1.0, tolerance=0.02)
        assert result == 0.0  # always within band

    def test_valid_n_tail_works(self):
        from core.evaluation.metrics import steady_state_error
        result = steady_state_error([1.0, 1.1, 1.0], setpoint=1.0, n_tail=2)
        assert abs(result - 0.05) < 1e-10
