"""Robustness tests — hardening code quality and closing remaining gaps.
鲁棒性测试 — 加固代码质量并关闭剩余缺口。
"""

import pytest
import numpy as np


# ---------- Config Error Paths ----------

class TestConfigErrorPaths:
    """Test error handling in core.config."""

    def test_load_json_missing_file(self):
        """_load_json raises FileNotFoundError for missing file."""
        from core.config import _load_json
        with pytest.raises(FileNotFoundError, match="not found"):
            _load_json("nonexistent_file.json")

    def test_load_sample_timeseries_exists(self):
        """Verify CSV loader returns expected columns."""
        from core.config import load_sample_timeseries
        data = load_sample_timeseries()
        assert set(data.keys()) == {"time", "inflow", "water_level", "water_level_observed"}


# ---------- Error Message Consistency ----------

class TestErrorMessageConsistency:
    """Verify all 'Unknown ...' errors include valid options."""

    def test_design_server_unknown_method(self):
        from mcp_servers.design_server import run_sensitivity
        with pytest.raises(ValueError, match="Use 'OAT' or 'Morris'"):
            run_sensitivity(
                base_params={"area": 1.0},
                param_ranges={"area": [0.5, 1.5]},
                method="invalid",
            )

    def test_scheduling_server_unknown_method(self):
        from mcp_servers.scheduling_server import optimize_schedule
        with pytest.raises(ValueError, match="Use 'lp' or 'rule'"):
            optimize_schedule(demand_forecast=[0.01], method="invalid")

    def test_distributed_optim_unknown_method(self):
        from compute.distributed_optim import parallel_sensitivity
        with pytest.raises(ValueError, match="Use 'OAT' or 'Morris'"):
            parallel_sensitivity(
                param_ranges={"area": (0.5, 1.5)},
                evaluate_fn=lambda p: 1.0,
                method="invalid",
            )

    def test_prediction_server_unknown_model(self):
        from mcp_servers.prediction_server import predict_future
        with pytest.raises(ValueError, match="Use 'linear', 'polynomial', or 'lstm'"):
            predict_future(historical_data=[1.0, 2.0, 3.0], model="arima")


# ---------- Monte Carlo std Validation ----------

class TestMonteCarloValidation:
    """Test monte_carlo_sim input validation."""

    def test_negative_std_raises(self):
        from compute.distributed_sim import monte_carlo_sim
        with pytest.raises(ValueError, match="non-negative"):
            monte_carlo_sim(
                base_params={"duration": 10, "dt": 1.0},
                vary_params={"cd": (0.6, -0.1)},
                n_samples=5,
                use_ray=False,
            )

    def test_zero_std_is_valid(self):
        """std=0 should produce identical parameters each sample."""
        from compute.distributed_sim import monte_carlo_sim
        results = monte_carlo_sim(
            base_params={"duration": 10, "dt": 1.0},
            vary_params={"cd": (0.6, 0.0)},
            n_samples=3,
            use_ray=False,
            seed=42,
        )
        assert len(results) == 3


# ---------- Prediction Server Degree Passthrough ----------

class TestPredictionDegreePassthrough:
    """Test polynomial degree parameter in predict_future."""

    def test_degree_default(self):
        from mcp_servers.prediction_server import predict_future
        data = [0.5 + 0.01 * i for i in range(50)]
        result = predict_future(data, horizon=5, model="polynomial")
        assert len(result["predictions"]) == 5

    def test_degree_3(self):
        from mcp_servers.prediction_server import predict_future
        data = [0.5 + 0.01 * i + 0.0001 * i**2 for i in range(50)]
        result = predict_future(data, horizon=5, model="polynomial", degree=3)
        assert "polynomial" in result["method"]
        assert len(result["predictions"]) == 5

    def test_lookback_parameter(self):
        from mcp_servers.prediction_server import predict_future
        data = [0.5 + 0.01 * i for i in range(100)]
        result = predict_future(data, horizon=5, model="linear", lookback=20)
        assert len(result["predictions"]) == 5


# ---------- Morris Sensitivity via Compute Layer ----------

class TestParallelSensitivityMorris:
    """Test parallel_sensitivity with Morris method."""

    def test_morris_via_compute(self):
        from compute.distributed_optim import parallel_sensitivity
        result = parallel_sensitivity(
            param_ranges={"x": (0.0, 1.0), "y": (0.0, 1.0)},
            evaluate_fn=lambda p: p["x"] ** 2 + p["y"],
            method="Morris",
            n_levels=4,
            n_trajectories=5,
            seed=42,
        )
        assert result["method"] == "Morris"
        assert "x" in result["parameters"]
        assert "y" in result["parameters"]
        assert "mu_star" in result["parameters"]["x"]


# ---------- Report Agent MPC Controller Type ----------

class TestReportAgentMPC:
    """Test report generation with MPC controller type."""

    def test_control_report_mpc(self):
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "performance_metrics": {"RMSE": 0.02, "OVERSHOOT": 5.0, "SETTLING_TIME": 120.0},
            "control_simulation": {
                "setpoint": 1.0,
                "water_level": [0.5, 0.8, 1.05, 1.02, 1.0],
                "metadata": {"solver": "Euler+MPC", "steps": 300, "dt": 1.0},
            },
            "controller_type": "MPC",
        }
        report = agent.generate_control_report(results)
        assert "MPC" in report
        assert "RMSE" in report
        assert "OVERSHOOT" in report

    def test_odd_report_with_mrc_plan(self):
        """ODD report should render MRC plan section."""
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "current_odd_status": {"zone": "mrc", "n_violations": 2},
            "overall_assessment": {
                "scenarios_tested": 5,
                "scenarios_with_violations": 3,
                "safety_rating": "critical",
            },
            "mrc_plan": {
                "severity": "critical",
                "actions": [
                    {"priority": "high", "description": "Reduce inflow immediately"},
                    {"priority": "medium", "description": "Alert operator"},
                ],
            },
        }
        report = agent.generate_odd_report(results)
        assert "MRC Plan" in report
        assert "critical" in report
        assert "Reduce inflow immediately" in report
        assert "Alert operator" in report

    def test_control_report_none_metric(self):
        """Metrics with None value should render as N/A."""
        from agents.report_agent import ReportAgent
        agent = ReportAgent()
        results = {
            "performance_metrics": {"SETTLING_TIME": None, "MAE": 0.01},
            "control_simulation": {
                "setpoint": 1.0,
                "water_level": [0.5, 1.0],
                "metadata": {"solver": "Euler", "steps": 50, "dt": 1.0},
            },
            "controller_type": "PID",
        }
        report = agent.generate_control_report(results)
        assert "N/A" in report
        assert "MAE" in report


# ---------- Safety Agent Multi-Dimension Violations ----------

class TestSafetyAgentMultiDim:
    """Test safety agent with simultaneous multi-dimension violations."""

    def test_multi_dim_mrc(self):
        """Both water_level and inflow_rate breaching should trigger MRC."""
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        result = agent.check_state({
            "water_level": 3.0,  # way above max (1.8)
            "inflow_rate": 0.1,  # above max (0.05)
        })
        assert result["zone"] == "mrc"
        assert len(result["violations"]) >= 2

    def test_multi_dim_extended(self):
        """State near boundary on multiple dims → extended zone."""
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        result = agent.check_state({
            "water_level": 0.15,  # near lower boundary
            "inflow_rate": 0.048,  # near upper boundary
        })
        # At least extended zone
        assert result["zone"] in ("extended", "mrc")

    def test_check_action_extended_zone(self):
        """Action check in extended zone should require human confirmation."""
        from agents.safety_agent import SafetyAgent
        agent = SafetyAgent()
        result = agent.check_action_safe(
            action={"type": "set_inflow", "value": 0.03},
            current_state={"water_level": 0.15},
        )
        assert result["zone"] == "extended"
        assert result["requires_human_confirmation"] is True
        assert result["proposed_action_blocked"] is False


# ---------- Analysis Agent Extended ----------

class TestAnalysisAgentExtended:
    """Extended analysis agent tests."""

    @pytest.mark.asyncio
    async def test_compare_schemes_with_custom_metrics(self):
        from agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent()
        schemes = [
            {"duration": 50, "q_in_profile": [[0, 0.01]], "initial_h": 0.3},
            {"duration": 50, "q_in_profile": [[0, 0.02]], "initial_h": 0.3},
            {"duration": 50, "q_in_profile": [[0, 0.03]], "initial_h": 0.3},
        ]
        result = await agent.compare_schemes(
            schemes,
            metrics=["RMSE", "NSE"],
            weights={"RMSE": 0.7, "NSE": 0.3},
        )
        assert result["n_schemes"] == 3
        assert len(result["ranking"]) == 3
        # Ranking should be ordered by final_level descending
        levels = [r["final_level"] for r in result["results"]]
        assert levels[result["ranking"][0]] >= levels[result["ranking"][-1]]

    @pytest.mark.asyncio
    async def test_viz_control_comparison(self):
        from agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent()
        code = await agent.generate_visualization_code({}, plot_type="control_comparison")
        assert "matplotlib" in code
        assert "Controller Comparison" in code

    @pytest.mark.asyncio
    async def test_viz_unsupported_type(self):
        from agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent()
        code = await agent.generate_visualization_code({}, plot_type="scatter_3d")
        assert "Unsupported" in code


# ---------- MPC Control Simulation Full ----------

class TestMPCControlSimulation:
    """Test MPC closed-loop control simulation."""

    def test_run_mpc_control_basic(self):
        from core.control.mpc_controller import run_mpc_control
        result = run_mpc_control(
            setpoint=1.0,
            initial_h=0.5,
            duration=100,
            dt=1.0,
        )
        assert "water_level" in result
        assert "control_output" in result
        assert result["metadata"]["solver"] == "Euler+MPC"
        # MPC should drive level towards setpoint
        assert result["water_level"][-1] > result["water_level"][0]

    def test_mpc_controller_reset(self):
        from core.control.mpc_controller import MPCController
        mpc = MPCController(horizon=5)
        mpc.compute(0.5, 1.0)
        assert len(mpc.get_history()) == 1
        mpc.reset()
        assert len(mpc.get_history()) == 0

    def test_mpc_via_control_server(self):
        """MPC through MCP control server."""
        from mcp_servers.control_server import run_controller
        result = run_controller(
            setpoint=1.0,
            controller_type="MPC",
            simulation_config={"duration": 50, "dt": 1.0, "initial_h": 0.5},
        )
        assert "water_level" in result
        assert result["metadata"]["solver"] == "Euler+MPC"

    def test_mpc_single_step_via_server(self):
        """MPC single-step mode through server."""
        from mcp_servers.control_server import run_controller
        result = run_controller(
            setpoint=1.0,
            current_state={"h": 0.5, "q_out": 0.005},
            controller_type="MPC",
        )
        assert "control_output" in result
        assert result["control_output"] >= 0


# ---------- Parallel Evaluate ----------

class TestParallelEvaluate:
    """Test parallel_evaluate edge cases."""

    def test_empty_param_list(self):
        from compute.distributed_optim import parallel_evaluate
        result = parallel_evaluate([], lambda p: 1.0, use_ray=False)
        assert result == []

    def test_basic_evaluation(self):
        from compute.distributed_optim import parallel_evaluate
        result = parallel_evaluate(
            [{"x": 1}, {"x": 2}, {"x": 3}],
            lambda p: p["x"] ** 2,
            use_ray=False,
        )
        assert result == [1, 4, 9]


# ---------- ODD Definition Edge Cases ----------

class TestODDDefinitionEdgeCases:
    """Test ODD spec edge cases."""

    def test_get_dimension_missing(self):
        from core.odd.odd_definition import ODDSpec
        spec = ODDSpec()
        spec.add_dimension("water_level", 0.0, 2.0, "m")
        assert spec.get_dimension("nonexistent") is None

    def test_from_dict_with_warning_margin(self):
        from core.odd.odd_definition import ODDSpec
        data = {
            "dimensions": [
                {"name": "water_level", "min_value": 0.0, "max_value": 2.0,
                 "unit": "m", "warning_margin": 0.2},
            ]
        }
        spec = ODDSpec.from_dict(data)
        dim = spec.get_dimension("water_level")
        assert dim.warning_margin == 0.2
        assert dim.warning_lower == 0.0 + 0.2 * 2.0  # 0.4
        assert dim.warning_upper == 2.0 - 0.2 * 2.0  # 1.6


# ---------- Evaluation evaluate_performance Control Metrics ----------

class TestEvaluatePerformanceControl:
    """Test evaluate_performance with control-specific metrics."""

    def test_all_control_metrics(self):
        from core.evaluation.metrics import evaluate_performance
        time = list(range(20))
        response = [0.0, 0.3, 0.6, 0.9, 1.1, 1.05, 1.02, 1.01] + [1.0] * 12
        reference = [1.0] * 20
        result = evaluate_performance(
            observed=reference,
            predicted=response,
            metrics_list=["RMSE", "SETTLING_TIME", "OVERSHOOT", "STEADY_STATE_ERROR"],
            time_series=time,
            setpoint=1.0,
        )
        assert "RMSE" in result
        assert "SETTLING_TIME" in result
        assert "OVERSHOOT" in result
        assert "STEADY_STATE_ERROR" in result
        assert result["OVERSHOOT"] > 0  # has overshoot at 1.1
        assert abs(result["STEADY_STATE_ERROR"]) < 0.05

    def test_mape_all_zeros(self):
        """MAPE with all-zero observed should return inf."""
        from core.evaluation.metrics import mape
        result = mape([0.0, 0.0, 0.0], [0.1, 0.2, 0.3])
        assert result == float("inf")


# ---------- WNAL Boundary Cases ----------

class TestWNALBoundary:
    """Test WNAL assessor at level boundaries."""

    def test_l2_boundary(self):
        from core.evaluation import assess_wnal
        # Score around 40-55 → L2
        caps = {k: 50.0 for k in [
            "sensing", "communication", "modeling",
            "prediction", "control", "odd_monitoring", "decision_support",
        ]}
        result = assess_wnal(caps)
        assert result["level"] == "L2"

    def test_l3_boundary(self):
        from core.evaluation import assess_wnal
        # Score around 55-70 → L3
        caps = {k: 65.0 for k in [
            "sensing", "communication", "modeling",
            "prediction", "control", "odd_monitoring", "decision_support",
        ]}
        result = assess_wnal(caps)
        assert result["level"] == "L3"

    def test_capability_clamping(self):
        """Scores above 100 should be clamped to 100."""
        from core.evaluation import assess_wnal
        caps = {"sensing": 150.0, "control": -10.0}
        result = assess_wnal(caps)
        # sensing clamped to 100, control clamped to 0
        details = {d["capability"]: d for d in result["details"]}
        assert details["sensing"]["raw_score"] == 100.0
        assert details["control"]["raw_score"] == 0.0


# ---------- Sensitivity Morris Core ----------

class TestSensitivityMorrisCore:
    """Test Morris sensitivity at the core level."""

    def test_morris_basic(self):
        from core.design.sensitivity import sensitivity_morris
        result = sensitivity_morris(
            param_ranges={"a": (0.0, 1.0), "b": (0.0, 2.0)},
            evaluate_fn=lambda p: 3 * p["a"] + p["b"],
            n_trajectories=8,
            n_levels=4,
            seed=123,
        )
        assert result["method"] == "Morris"
        # 'a' should have higher mu_star than 'b' roughly 3x impact
        assert result["parameters"]["a"]["mu_star"] > 0
        assert result["parameters"]["b"]["mu_star"] > 0

    def test_morris_n_levels_too_low(self):
        from core.design.sensitivity import sensitivity_morris
        with pytest.raises(ValueError, match="at least 2"):
            sensitivity_morris(
                param_ranges={"a": (0.0, 1.0)},
                evaluate_fn=lambda p: p["a"],
                n_levels=1,
            )


# ---------- create_mpc_actor Return Type ----------

class TestCreateMpcActorAnnotation:
    """Verify create_mpc_actor has proper type annotation."""

    def test_return_type_annotation_exists(self):
        from compute.actor_controller import create_mpc_actor
        import inspect
        sig = inspect.signature(create_mpc_actor)
        # Should have a return annotation (Any)
        assert sig.return_annotation is not inspect.Parameter.empty


# ---------- Skill Control System Design with MPC ----------

class TestControlSystemDesignMPC:
    """Test ControlSystemDesignSkill with MPC controller."""

    @pytest.mark.asyncio
    async def test_skill_with_mpc(self):
        from skills.control_system_design import ControlSystemDesignSkill
        skill = ControlSystemDesignSkill()
        result = await skill.run({
            "controller_type": "MPC",
            "setpoint": 1.0,
            "duration": 100,
            "dt": 1.0,
        })
        assert result.success
        assert "closed_loop_control" in result.steps_completed
        assert result.data["controller_type"] == "MPC"


# ---------- NSE Edge Case ----------

class TestNSEEdgeCases:
    """Test Nash-Sutcliffe Efficiency edge cases."""

    def test_constant_observed(self):
        """If observed is constant and pred matches, NSE = 1."""
        from core.evaluation.metrics import nse
        obs = [1.0, 1.0, 1.0, 1.0]
        pred = [1.0, 1.0, 1.0, 1.0]
        assert nse(obs, pred) == 1.0

    def test_constant_observed_poor_pred(self):
        """If observed is constant but pred differs, NSE = large negative finite value."""
        from core.evaluation.metrics import nse
        obs = [1.0, 1.0, 1.0, 1.0]
        pred = [0.5, 1.5, 0.5, 1.5]
        result = nse(obs, pred)
        assert result == -1e6
