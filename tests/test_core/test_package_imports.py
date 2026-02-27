"""Tests for package __init__.py exports — ensures public API stays stable.
包导出测试 — 确保公共 API 保持稳定。
"""



class TestCoreSimulationExports:
    def test_exports(self):
        from core.simulation import (
            GRAVITY,
            TankParams,
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
            PIDController,
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
        from core.design import optimize_tank_size, sensitivity_morris, sensitivity_oat
        assert callable(optimize_tank_size)
        assert callable(sensitivity_oat)
        assert callable(sensitivity_morris)


class TestCoreEvaluationExports:
    def test_exports(self):
        from core.evaluation import (
            CAPABILITY_WEIGHTS,
            LEVEL_THRESHOLDS,
            rmse,
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
            detect_3sigma,
            interpolate_linear,
        )
        assert callable(interpolate_linear)
        assert callable(detect_3sigma)


class TestCoreODDExports:
    def test_exports(self):
        from core.odd import (
            create_tank_odd,
        )
        odd = create_tank_odd()
        assert len(odd.dimensions) == 6

    def test_zone_type(self):
        from core.odd import Zone
        assert Zone is not None


class TestCoreIdentificationExports:
    def test_exports(self):
        from core.identification import identify_arx, identify_tank_params
        assert callable(identify_arx)
        assert callable(identify_tank_params)


class TestCoreTopLevelExports:
    def test_config_functions(self):
        from core import (
            load_tank_config,
        )
        config = load_tank_config()
        assert "tank_params" in config


class TestComputeExports:
    def test_exports(self):
        from compute import (
            init_ray,
            parameter_sweep,
        )
        assert callable(init_ray)
        assert callable(parameter_sweep)


class TestSkillsExports:
    def test_base_classes(self):
        from skills import SkillResult, discover_skills
        assert callable(discover_skills)
        result = SkillResult(success=True, data={"test": 1})
        assert result.success

    def test_skill_classes(self):
        from skills import (
            ForecastSkill,
            FourPredictionLoopSkill,
        )
        assert ForecastSkill is not None
        assert FourPredictionLoopSkill is not None


class TestAgentsExports:
    def test_exports(self):
        from agents import (
            TOOL_KEYWORDS,
        )
        assert isinstance(TOOL_KEYWORDS, dict)
        assert "simulate_tank" in TOOL_KEYWORDS
