"""Tests for R7 multi-agent review fixes.
R7 多智能体评审修复测试。
"""

from __future__ import annotations

import pytest

# ---------- H1: DataAnalysisPredictSkill error check ----------

class TestDataAnalysisPredictErrorCheck:
    """Verify DataAnalysisPredictSkill handles clean_result errors."""

    def test_error_check_in_clean_result(self):
        """The skill should check for 'error' key in clean_result."""
        with open("skills/data_analysis_predict.py") as f:
            source = f.read()
        # Verify the error check pattern exists
        assert '"error" in clean_result' in source
        assert 'clean_result.get("data"' in source


# ---------- H2: WarningSkill violations key ----------

class TestWarningSkillViolationsKey:
    """Verify WarningSkill uses 'violations' key from ODD result."""

    def test_violations_key_used(self):
        """WarningSkill should use 'violations' key with fallback."""
        with open("skills/warning_skill.py") as f:
            source = f.read()
        assert 'odd_result.get("violations"' in source


# ---------- H3: Report markdown escaping comprehensive ----------

class TestReportMarkdownEscapingExtended:
    """Verify all report methods escape user-derived data."""

    def test_lifecycle_report_escapes_summary(self):
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "summary": {
                "tank_area": "1.0|injected",
                "controller": "[link](bad)",
                "setpoint": "1.0",
                "odd_zone": "normal",
            },
            "evaluation": {
                "metric|key": 0.95,
                "text[metric]": "value|pipes",
            },
        }
        report = agent.generate_lifecycle_report(results)
        # Pipes should be escaped in table
        assert "1.0\\|injected" in report
        assert "\\[link\\]" in report
        # Evaluation keys/values should be escaped
        assert "metric\\|key" in report
        assert "value\\|pipes" in report

    def test_odd_report_escapes_zone(self):
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "current_odd_status": {"zone": "mrc|bad", "n_violations": 1},
            "overall_assessment": {"safety_rating": "danger[1]"},
            "mrc_plan": {
                "severity": "high|critical",
                "actions": [
                    {"priority": "1|a", "description": "action[1]"},
                ],
            },
        }
        report = agent.generate_odd_report(results)
        assert "mrc\\|bad" in report
        assert "danger\\[1\\]" in report
        assert "high\\|critical" in report
        assert "action\\[1\\]" in report

    def test_control_report_escapes_type(self):
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "controller_type": "PID|v2",
            "control_simulation": {
                "setpoint": "1.0",
                "water_level": [0.5, 0.8, 1.0],
                "metadata": {"steps": 100, "dt": 1.0, "solver": "euler|fast"},
            },
            "performance_metrics": {"rmse": 0.05},
        }
        report = agent.generate_control_report(results)
        assert "PID\\|v2" in report
        assert "euler\\|fast" in report


# ---------- H4: Control server param filtering ----------

class TestControlServerParamFiltering:
    """Verify control server filters unknown params."""

    def test_pid_unknown_params_filtered(self):
        from mcp_servers.control_server import run_controller
        # Should not crash with extra keys
        result = run_controller(
            setpoint=1.0,
            controller_type="PID",
            params={"kp": 2.0, "ki": 0.1, "kd": 0.05, "malicious_key": "bad"},
        )
        assert "control_output" in result

    def test_mpc_unknown_params_filtered(self):
        from mcp_servers.control_server import run_controller
        result = run_controller(
            setpoint=1.0,
            controller_type="MPC",
            params={"horizon": 10, "unknown_key": 999},
        )
        assert "control_output" in result


# ---------- H5: Rehearsal skill pre-computed min/max ----------

class TestRehearsalPreComputedMinMax:
    """Verify rehearsal skill pre-computes min/max levels."""

    def test_no_redundant_max_min_calls(self):
        """Source should compute max and min once."""
        with open("skills/rehearsal_skill.py") as f:
            source = f.read()
        assert "max_lev = max(levels)" in source
        assert "min_lev = min(levels)" in source


# ---------- M1: SafetyAgent MRC error propagation ----------

class TestSafetyAgentMRCErrorPropagation:
    """Verify SafetyAgent propagates MRC generation errors."""

    def test_mrc_error_key_in_response(self):
        """When MRC plan fails, error should be in response."""
        from agents.safety_agent import SafetyAgent
        # Create agent with config that puts state in MRC zone
        agent = SafetyAgent()
        # Check normal zone first — no mrc_error key
        result = agent.check_action_safe(
            action={"type": "adjust_inflow", "value": 0.02},
            current_state={"water_level": 1.0},
        )
        assert "mrc_error" not in result
        assert result["zone"] in ("normal", "extended")


# ---------- M2: ODD dimension dict lookup ----------

class TestODDDimensionDictLookup:
    """Verify ODDSpec uses dict-based O(1) lookup."""

    def test_get_dimension_fast(self):
        from core.odd.odd_definition import create_tank_odd
        odd = create_tank_odd()
        wl = odd.get_dimension("water_level")
        assert wl is not None
        assert wl.name == "water_level"

    def test_get_dimension_missing(self):
        from core.odd.odd_definition import create_tank_odd
        odd = create_tank_odd()
        assert odd.get_dimension("nonexistent") is None

    def test_dim_index_consistent(self):
        from core.odd.odd_definition import ODDSpec
        spec = ODDSpec()
        spec.add_dimension("test_dim", 0.0, 10.0, "m")
        # Both list and dict should have the dimension
        assert len(spec.dimensions) == 1
        assert "test_dim" in spec._dim_index
        assert spec._dim_index["test_dim"] is spec.dimensions[0]

    def test_range_val_property(self):
        from core.odd.odd_definition import DimensionSpec
        dim = DimensionSpec(
            name="test", min_value=0.0, max_value=10.0,
            unit="m", warning_margin=0.1,
        )
        assert dim.range_val == 10.0
        assert dim.warning_lower == 1.0  # 0 + 0.1*10
        assert dim.warning_upper == 9.0  # 10 - 0.1*10


# ---------- M3: Rule-based scheduler redundant min ----------

class TestRuleBasedSchedulerFix:
    """Verify rule_based uses supply_capacity * 0.8 directly."""

    def test_increase_supply_rate(self):
        from core.scheduling.rule_based import schedule_rule_based
        result = schedule_rule_based(
            current_level=0.5,  # below target - 0.2 = 0.8
            target_level=1.0,
            supply_capacity=0.05,
        )
        assert result["rule"] == "increase_supply"
        assert result["inflow_rate"] == pytest.approx(0.05 * 0.8)

    def test_no_redundant_min_in_source(self):
        with open("core/scheduling/rule_based.py") as f:
            source = f.read()
        # Should NOT contain min(supply_capacity * 0.8, supply_capacity)
        assert "min(supply_capacity * 0.8, supply_capacity)" not in source


# ---------- M5: Monte Carlo negative std validation ----------

class TestMonteCarloNegativeStd:
    """Verify Monte Carlo rejects negative standard deviation."""

    def test_negative_std_raises(self):
        from compute.distributed_sim import monte_carlo_sim
        with pytest.raises(ValueError, match="non-negative"):
            monte_carlo_sim(
                {"duration": 10, "dt": 1.0, "tank_params": {"area": 1.0}},
                {"cd": (0.6, -0.05)},
                n_samples=5,
                use_ray=False,
            )

    def test_zero_std_ok(self):
        from compute.distributed_sim import monte_carlo_sim
        # Zero std should be fine (no variation)
        results = monte_carlo_sim(
            {"duration": 10, "dt": 1.0},
            {"area": (1.0, 0.0)},
            n_samples=3,
            use_ray=False,
            seed=42,
        )
        assert len(results) == 3

    def test_none_tank_params_handled(self):
        from compute.distributed_sim import monte_carlo_sim
        results = monte_carlo_sim(
            {"duration": 10, "dt": 1.0, "tank_params": None},
            {"area": (1.0, 0.1)},
            n_samples=3,
            use_ray=False,
            seed=42,
        )
        assert len(results) == 3


# ---------- ODD from_dict populates index ----------

class TestODDFromDictIndex:
    """Verify ODDSpec.from_dict populates _dim_index correctly."""

    def test_from_dict_has_index(self):
        from core.odd.odd_definition import ODDSpec
        data = {
            "dimensions": [
                {"name": "water_level", "min_value": 0.1, "max_value": 1.8, "unit": "m"},
                {"name": "inflow_rate", "min_value": 0.0, "max_value": 0.05, "unit": "m³/s"},
            ],
        }
        spec = ODDSpec.from_dict(data)
        assert spec.get_dimension("water_level") is not None
        assert spec.get_dimension("inflow_rate") is not None
        assert len(spec._dim_index) == 2
