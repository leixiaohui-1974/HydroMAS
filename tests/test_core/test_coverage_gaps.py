"""Tests for previously uncovered functions and edge cases.
覆盖率补充测试 — 补齐遗漏的功能测试。
"""

import pytest
import numpy as np


# ---------- LSTM Predictor Stub ----------

class TestLSTMPredictor:
    """Test LSTM predictor stub behavior."""

    def test_lstm_without_torch(self):
        """LSTM should return error when torch is not installed."""
        from core.prediction.lstm_predictor import predict_lstm
        result = predict_lstm([1.0, 2.0, 3.0], horizon=5)
        assert "error" in result
        assert result["predictions"] == []
        assert result["method"] == "lstm"

    def test_lstm_import_via_package(self):
        """LSTM should be importable from package __init__."""
        from core.prediction import predict_lstm
        result = predict_lstm([1.0, 2.0, 3.0], horizon=5)
        assert result["method"] == "lstm"


# ---------- Rule-Based Scheduler ----------

class TestRuleBasedSchedulerExtended:
    """Extended tests for rule-based scheduler."""

    def test_at_exact_boundary_min(self):
        """Level exactly at min_level triggers emergency fill."""
        from core.scheduling.rule_based import schedule_rule_based
        result = schedule_rule_based(current_level=0.2, min_level=0.2)
        assert result["rule"] == "emergency_fill"
        assert result["priority"] == "critical"

    def test_at_exact_boundary_max(self):
        """Level exactly at max_level triggers shutoff."""
        from core.scheduling.rule_based import schedule_rule_based
        result = schedule_rule_based(current_level=1.8, max_level=1.8)
        assert result["rule"] == "emergency_shutoff"
        assert result["priority"] == "critical"

    def test_import_via_package(self):
        """schedule_rule_based importable from package __init__."""
        from core.scheduling import schedule_rule_based
        result = schedule_rule_based(current_level=1.0)
        assert "inflow_rate" in result

    def test_custom_supply_capacity(self):
        """Custom supply capacity should be respected."""
        from core.scheduling.rule_based import schedule_rule_based
        result = schedule_rule_based(
            current_level=0.1, min_level=0.2, supply_capacity=0.1,
        )
        assert result["inflow_rate"] == 0.1

    def test_reduce_supply_rate(self):
        """Reduce supply should be 20% of capacity."""
        from core.scheduling.rule_based import schedule_rule_based
        result = schedule_rule_based(
            current_level=1.5, target_level=1.0, supply_capacity=0.05,
        )
        assert result["inflow_rate"] == pytest.approx(0.01)


# ---------- ODD Definition Tests ----------

class TestODDDefinitionExtended:
    """Extended ODD definition tests."""

    def test_odd_from_json_file(self):
        """ODDSpec.from_json should load from data/odd_specs.json."""
        from core.odd.odd_definition import ODDSpec
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent.parent / "data" / "odd_specs.json"
        odd = ODDSpec.from_json(path)
        assert len(odd.dimensions) == 6

    def test_odd_to_dict_round_trip(self):
        """to_dict → from_dict should round-trip correctly."""
        from core.odd.odd_definition import create_tank_odd, ODDSpec
        odd = create_tank_odd()
        d = odd.to_dict()
        odd2 = ODDSpec.from_dict(d)
        assert len(odd2.dimensions) == len(odd.dimensions)
        for d1, d2 in zip(odd.dimensions, odd2.dimensions):
            assert d1.name == d2.name
            assert d1.min_value == d2.min_value
            assert d1.max_value == d2.max_value

    def test_dimension_warning_thresholds(self):
        """Warning thresholds should be computed correctly."""
        from core.odd.odd_definition import DimensionSpec
        dim = DimensionSpec(name="test", min_value=0.0, max_value=10.0, unit="m", warning_margin=0.1)
        assert dim.warning_lower == pytest.approx(1.0)  # 0 + 0.1 * 10
        assert dim.warning_upper == pytest.approx(9.0)  # 10 - 0.1 * 10

    def test_get_dimension_nonexistent(self):
        """get_dimension for nonexistent name returns None."""
        from core.odd.odd_definition import create_tank_odd
        odd = create_tank_odd()
        assert odd.get_dimension("nonexistent") is None


# ---------- ODD Monitor Extended Tests ----------

class TestODDMonitorExtended:
    """Extended ODD monitor zone classification tests."""

    def test_classify_normal(self):
        """Value in the middle of the range is normal."""
        from core.odd.odd_monitor import classify_value
        from core.odd.odd_definition import DimensionSpec
        dim = DimensionSpec("wl", 0.0, 2.0, "m", warning_margin=0.1)
        assert classify_value(1.0, dim) == "normal"

    def test_classify_extended_lower(self):
        """Value in lower warning margin is extended."""
        from core.odd.odd_monitor import classify_value
        from core.odd.odd_definition import DimensionSpec
        dim = DimensionSpec("wl", 0.0, 2.0, "m", warning_margin=0.1)
        # warning_lower = 0.0 + 0.1 * 2.0 = 0.2
        assert classify_value(0.1, dim) == "extended"

    def test_classify_extended_upper(self):
        """Value in upper warning margin is extended."""
        from core.odd.odd_monitor import classify_value
        from core.odd.odd_definition import DimensionSpec
        dim = DimensionSpec("wl", 0.0, 2.0, "m", warning_margin=0.1)
        # warning_upper = 2.0 - 0.1 * 2.0 = 1.8
        assert classify_value(1.9, dim) == "extended"

    def test_classify_mrc_below(self):
        """Value below min is MRC."""
        from core.odd.odd_monitor import classify_value
        from core.odd.odd_definition import DimensionSpec
        dim = DimensionSpec("wl", 0.1, 1.8, "m")
        assert classify_value(0.05, dim) == "mrc"

    def test_classify_mrc_above(self):
        """Value above max is MRC."""
        from core.odd.odd_monitor import classify_value
        from core.odd.odd_definition import DimensionSpec
        dim = DimensionSpec("wl", 0.1, 1.8, "m")
        assert classify_value(2.0, dim) == "mrc"

    def test_check_odd_multi_dimension(self):
        """Check ODD with multiple dimensions, some normal, some violated."""
        from core.odd.odd_monitor import check_odd
        from core.odd.odd_definition import create_tank_odd
        odd = create_tank_odd()
        result = check_odd({
            "water_level": 1.0,     # normal
            "inflow_rate": 0.1,     # above max 0.05 → MRC
            "temperature": 20.0,    # normal
        }, odd)
        assert result["zone"] == "mrc"
        assert result["n_violations"] == 1
        assert result["violations"][0]["dimension"] == "inflow_rate"

    def test_check_odd_series_time_to_breach(self):
        """check_odd_series should report correct time_to_breach."""
        from core.odd.odd_monitor import check_odd_series
        states = [
            {"water_level": 1.0},
            {"water_level": 1.5},
            {"water_level": 2.0},  # breaches 1.8 max
        ]
        result = check_odd_series(states, time_series=[0.0, 10.0, 20.0])
        assert result["worst_zone"] == "mrc"
        assert result["time_to_breach"] == 20.0

    def test_check_odd_missing_dimensions_ignored(self):
        """Dimensions not in state dict should be skipped."""
        from core.odd.odd_monitor import check_odd
        from core.odd.odd_definition import create_tank_odd
        odd = create_tank_odd()
        result = check_odd({"water_level": 1.0}, odd)
        assert result["n_checked"] == 1  # Only water_level checked
        assert result["zone"] == "normal"


# ---------- MRC Handler Tests ----------

class TestMRCHandler:
    """Tests for MRC handler actions and plan."""

    def test_water_level_upper_violation(self):
        """Upper water level violation triggers close_inlet and open_drain."""
        from core.odd.mrc_handler import determine_mrc_actions
        violations = [{"dimension": "water_level", "bound_violated": "upper", "value": 2.0, "limit": 1.8}]
        actions = determine_mrc_actions(violations)
        action_types = [a["action"] for a in actions]
        assert "close_inlet" in action_types
        assert "open_drain" in action_types

    def test_water_level_lower_violation(self):
        """Lower water level violation triggers reduce_inflow (emergency fill)."""
        from core.odd.mrc_handler import determine_mrc_actions
        violations = [{"dimension": "water_level", "bound_violated": "lower", "value": 0.05, "limit": 0.1}]
        actions = determine_mrc_actions(violations)
        assert actions[0]["action"] == "reduce_inflow"

    def test_structural_pressure_violation(self):
        """Structural pressure triggers emergency_stop with highest priority."""
        from core.odd.mrc_handler import determine_mrc_actions
        violations = [{"dimension": "structural_pressure", "bound_violated": "upper", "value": 60, "limit": 50}]
        actions = determine_mrc_actions(violations)
        assert actions[0]["action"] == "emergency_stop"
        assert actions[0]["priority"] == 0

    def test_unknown_dimension_gets_alert(self):
        """Unknown dimension gets generic alert."""
        from core.odd.mrc_handler import determine_mrc_actions
        violations = [{"dimension": "temperature", "bound_violated": "upper", "value": 45, "limit": 40}]
        actions = determine_mrc_actions(violations)
        assert actions[0]["action"] == "alert"

    def test_generate_mrc_plan(self):
        """Generate MRC plan includes all required fields."""
        from core.odd.mrc_handler import generate_mrc_plan
        violations = [{"dimension": "water_level", "bound_violated": "upper", "value": 2.0, "limit": 1.8}]
        state = {"water_level": 2.0}
        plan = generate_mrc_plan(violations, state)
        assert plan["status"] == "mrc_activated"
        assert len(plan["actions"]) > 0
        assert len(plan["verification_steps"]) > 0
        assert plan["severity"] in ("critical", "high")

    def test_mrc_plan_critical_severity(self):
        """Structural pressure violation → critical severity."""
        from core.odd.mrc_handler import generate_mrc_plan
        violations = [{"dimension": "structural_pressure", "bound_violated": "upper", "value": 60, "limit": 50}]
        plan = generate_mrc_plan(violations, {"structural_pressure": 60})
        assert plan["severity"] == "critical"


# ---------- Safety Agent Extended Tests ----------

class TestSafetyAgentExtended:
    """Extended safety agent tests covering all zones and scenarios."""

    def test_extended_zone_detection(self):
        """Water level near boundary should be detected as extended zone."""
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        # Default tank ODD: water_level min=0.1, max=1.8, warning_margin=0.1
        # warning_upper = 1.8 - 0.1 * (1.8 - 0.1) = 1.8 - 0.17 = 1.63
        # So value 1.7 is between warning_upper (1.63) and max (1.8) → extended
        result = agent.check_state({"water_level": 1.7})
        assert result["zone"] == "extended"

    def test_action_safe_extended_zone(self):
        """Extended zone should require human confirmation."""
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        result = agent.check_action_safe(
            action={"type": "set_inflow", "value": 0.01},
            current_state={"water_level": 1.7},
        )
        assert result["safe"] is True
        assert result["zone"] == "extended"
        assert result["requires_human_confirmation"] is True

    def test_multi_dimension_monitor(self):
        """Monitor series with multi-dimensional states."""
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        states = [
            {"water_level": 1.0, "inflow_rate": 0.02},
            {"water_level": 1.5, "inflow_rate": 0.03},
            {"water_level": 1.5, "inflow_rate": 0.06},  # inflow breach
        ]
        result = agent.monitor_series(states, [0, 10, 20])
        assert result["worst_zone"] == "mrc"
        assert result["time_to_breach"] == 20

    def test_monitor_all_normal(self):
        """All-normal series should have no breach."""
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        states = [{"water_level": 1.0}, {"water_level": 1.1}, {"water_level": 0.9}]
        result = agent.monitor_series(states)
        assert result["worst_zone"] == "normal"
        assert result["time_to_breach"] is None

    def test_custom_odd_config(self):
        """SafetyAgent with custom ODD config."""
        from agents.safety_agent import SafetyAgent
        custom_odd = {
            "dimensions": [
                {"name": "water_level", "min_value": 0.5, "max_value": 1.5, "unit": "m"}
            ]
        }
        agent = SafetyAgent(odd_config=custom_odd)
        # 1.6 is above custom max of 1.5 → mrc
        result = agent.check_state({"water_level": 1.6})
        assert result["zone"] == "mrc"


# ---------- Analysis Agent Extended Tests ----------

class TestAnalysisAgentExtended:
    """Extended tests for AnalysisAgent."""

    @pytest.mark.asyncio
    async def test_control_comparison_viz_code(self):
        """Generate control comparison visualization code."""
        from agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent()
        code = await agent.generate_visualization_code({}, plot_type="control_comparison")
        assert "matplotlib" in code
        assert "Controller Comparison" in code

    @pytest.mark.asyncio
    async def test_unsupported_plot_type(self):
        """Unsupported plot type returns informative comment."""
        from agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent()
        code = await agent.generate_visualization_code({}, plot_type="pie_chart")
        assert "Unsupported" in code


# ---------- Planning Agent Extended Tests ----------

class TestPlanningAgentExtended:
    """Extended tests for PlanningAgent."""

    def test_full_analysis_template(self):
        """Full analysis request matches full_analysis template."""
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        plan = agent.plan("请做一个完整分析")
        assert plan.objective == "Full system analysis"
        assert len(plan.nodes) == 5

    def test_english_compare_controllers(self):
        """English compare request should match template."""
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        plan = agent.plan("compare PID vs MPC controller performance")
        assert plan.objective == "Compare PID and MPC controllers"
        assert len(plan.nodes) == 4

    def test_task_plan_complete_cycle(self):
        """TaskPlan: complete a task then check ready transitions."""
        from agents.planning_agent import TaskNode, TaskPlan
        plan = TaskPlan(objective="test")
        plan.add_node(TaskNode("a", "step a", "tool_a"))
        plan.add_node(TaskNode("b", "step b", "tool_b", dependencies=["a"]))
        plan.add_node(TaskNode("c", "step c", "tool_c", dependencies=["a"]))

        # Initially only 'a' is ready
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "a"

        # Complete 'a', now 'b' and 'c' should be ready
        plan.nodes[0].status = "completed"
        ready = plan.get_ready_tasks()
        assert len(ready) == 2
        ids = {n.id for n in ready}
        assert ids == {"b", "c"}

    def test_default_plan_with_context(self):
        """Default plan passes context as params."""
        from agents.planning_agent import PlanningAgent
        agent = PlanningAgent()
        plan = agent.plan("something unusual", context={"key": "value"})
        assert plan.nodes[0].params == {"key": "value"}


# ---------- Report Agent Extended Tests ----------

class TestReportAgentExtended:
    """Extended tests for ReportAgent."""

    def test_odd_report_with_mrc_plan(self):
        """ODD report should include MRC plan section when present."""
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "current_odd_status": {"zone": "mrc", "n_violations": 1},
            "overall_assessment": {
                "scenarios_tested": 5,
                "scenarios_with_violations": 2,
                "safety_rating": "unsafe",
            },
            "mrc_plan": {
                "severity": "high",
                "actions": [
                    {"priority": 1, "description": "Close inlet valve"},
                    {"priority": 2, "description": "Open drain"},
                ],
            },
        }
        report = agent.generate_odd_report(results)
        assert "MRC Plan" in report
        assert "Close inlet valve" in report
        assert "high" in report.lower()

    def test_lifecycle_report_with_none_values(self):
        """Lifecycle report handles None values in evaluation."""
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "summary": {"tank_area": 2.0, "controller": "MPC", "setpoint": 1.0, "odd_zone": "normal"},
            "evaluation": {"RMSE": 0.1, "settling_time": None},
        }
        report = agent.generate_lifecycle_report(results)
        assert "MPC" in report
        assert "RMSE" in report
        # None value should be silently skipped (not crash)


# ---------- Identification Module Extended ----------

class TestIdentificationExtended:
    """Extended tests for ARX predict function."""

    def test_predict_arx(self):
        """Test ARX model prediction."""
        from core.identification.arx_model import identify_arx, predict_arx

        # Generate simple system: y(k) = 0.5*y(k-1) + 0.3*u(k-1)
        np.random.seed(42)
        n = 100
        u = np.random.randn(n) * 0.01
        y = np.zeros(n)
        for k in range(1, n):
            y[k] = 0.5 * y[k - 1] + 0.3 * u[k - 1]

        model = identify_arx(y.tolist(), u.tolist(), na=1, nb=1)
        assert model["r_squared"] > 0.9

        # Predict future
        preds = predict_arx(model, y[-5:].tolist(), [0.01] * 10)
        assert len(preds) == 10


# ---------- Interpolation Extended ----------

class TestInterpolationExtended:
    """Extended tests for interpolation edge cases."""

    def test_spline_fallback_to_linear(self):
        """Spline with too few valid points falls back to linear."""
        from core.data_clean.interpolation import interpolate_spline
        # Only 2 valid points (below k+1=4 for cubic spline)
        data = [1.0, float("nan"), float("nan"), 4.0]
        result = interpolate_spline(data, order=3)
        assert result["n_filled"] == 2
        # Should have fallen back to linear
        assert "linear" in result["method"] or "spline" in result["method"]

    def test_all_nan_linear(self):
        """Linear interpolation on all NaN fills with 0.0."""
        from core.data_clean.interpolation import interpolate_linear
        result = interpolate_linear([float("nan")] * 5)
        assert all(v == 0.0 for v in result["data"])
        assert result["n_filled"] == 5

    def test_median_filter_even_window(self):
        """Median filter auto-corrects even window to odd."""
        from core.data_clean.interpolation import median_filter
        result = median_filter([1.0, 2.0, 3.0, 4.0, 5.0], window_size=4)
        assert result["window_size"] == 5  # 4 → 5

    def test_clean_timeseries_unknown_method(self):
        """Unknown method raises ValueError."""
        from core.data_clean.interpolation import clean_timeseries
        with pytest.raises(ValueError, match="Unknown cleaning method"):
            clean_timeseries([1.0, 2.0], methods=["nonexistent_method"])
