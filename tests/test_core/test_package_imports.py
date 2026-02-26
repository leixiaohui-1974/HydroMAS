"""Tests for package __init__.py exports — ensures public API stays stable.
包导出测试 — 确保公共 API 保持稳定。
"""

import pytest


class TestCoreSimulationExports:
    def test_exports(self):
        from core.simulation import (
            GRAVITY, TankParams, compute_outflow, tank_ode,
            run_simulation, simulate_euler, simulate_rk4,
        )
        assert GRAVITY == 9.81
        assert TankParams is not None

    def test_all_list(self):
        import core.simulation
        assert hasattr(core.simulation, "__all__")
        assert "TankParams" in core.simulation.__all__
        assert "run_simulation" in core.simulation.__all__


class TestCoreControlExports:
    def test_exports(self):
        from core.control import (
            PIDParams, PIDController, run_pid_control,
            MPCController, run_mpc_control,
        )
        pid = PIDController()
        assert pid is not None

    def test_all_list(self):
        import core.control
        assert "PIDController" in core.control.__all__
        assert "MPCController" in core.control.__all__


class TestCorePredictionExports:
    def test_exports(self):
        from core.prediction import predict_linear, predict_polynomial
        assert callable(predict_linear)
        assert callable(predict_polynomial)


class TestCoreSchedulingExports:
    def test_exports(self):
        from core.scheduling import optimize_schedule_lp
        assert callable(optimize_schedule_lp)


class TestCoreDesignExports:
    def test_exports(self):
        from core.design import optimize_tank_size, sensitivity_oat, sensitivity_morris
        assert callable(optimize_tank_size)
        assert callable(sensitivity_oat)
        assert callable(sensitivity_morris)


class TestCoreEvaluationExports:
    def test_exports(self):
        from core.evaluation import (
            rmse, mae, nse, mape,
            settling_time, overshoot, steady_state_error,
            evaluate_performance,
            CAPABILITY_WEIGHTS, LEVEL_THRESHOLDS, assess_wnal,
        )
        assert callable(rmse)
        assert isinstance(CAPABILITY_WEIGHTS, dict)
        assert isinstance(LEVEL_THRESHOLDS, list)

    def test_all_list(self):
        import core.evaluation
        assert "rmse" in core.evaluation.__all__
        assert "assess_wnal" in core.evaluation.__all__


class TestCoreDataCleanExports:
    def test_exports(self):
        from core.data_clean import (
            interpolate_linear, interpolate_spline, median_filter,
            clean_timeseries,
            detect_3sigma, detect_iqr, detect_mad,
        )
        assert callable(interpolate_linear)
        assert callable(detect_3sigma)


class TestCoreODDExports:
    def test_exports(self):
        from core.odd import (
            DimensionSpec, ODDSpec, create_tank_odd,
            classify_value, check_odd, check_odd_series,
            determine_mrc_actions, generate_mrc_plan,
        )
        odd = create_tank_odd()
        assert len(odd.dimensions) == 6

    def test_zone_type(self):
        from core.odd import Zone
        assert Zone is not None


class TestCoreIdentificationExports:
    def test_exports(self):
        from core.identification import identify_arx, predict_arx, identify_tank_params
        assert callable(identify_arx)
        assert callable(identify_tank_params)


class TestCoreTopLevelExports:
    def test_config_functions(self):
        from core import (
            load_tank_config, load_odd_specs,
            get_default_tank_params, get_default_pid_params,
            get_default_mpc_params, get_default_simulation_params,
        )
        config = load_tank_config()
        assert "tank_params" in config


class TestComputeExports:
    def test_exports(self):
        from compute import (
            init_ray, shutdown_ray, is_ray_available,
            simulate_single, parameter_sweep, monte_carlo_sim,
            parallel_sensitivity, parallel_evaluate,
            parallel_clean, chunk_timeseries,
            create_mpc_actor,
        )
        assert callable(init_ray)
        assert callable(parameter_sweep)


class TestSkillsExports:
    def test_base_classes(self):
        from skills import BaseSkill, SkillResult, SkillMetadata, discover_skills
        assert callable(discover_skills)
        result = SkillResult(success=True, data={"test": 1})
        assert result.success

    def test_skill_classes(self):
        from skills import (
            ForecastSkill, WarningSkill, RehearsalSkill, PlanSkill,
            FourPredictionLoopSkill, DataAnalysisPredictSkill,
            ODDAssessmentSkill, ControlSystemDesignSkill,
            OptimizationDesignSkill, FullLifecycleSkill,
        )
        assert ForecastSkill is not None
        assert FourPredictionLoopSkill is not None


class TestAgentsExports:
    def test_exports(self):
        from agents import (
            OrchestratorAgent, TOOL_KEYWORDS,
            TaskNode, TaskPlan, PlanningAgent,
            AnalysisAgent, ReportAgent, SafetyAgent,
        )
        assert isinstance(TOOL_KEYWORDS, dict)
        assert "simulate_tank" in TOOL_KEYWORDS
