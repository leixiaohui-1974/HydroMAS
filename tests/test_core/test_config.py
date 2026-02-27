"""Tests for core.config — configuration loader utility.
配置加载器测试。
"""

from core.config import (
    get_default_mpc_params,
    get_default_pid_params,
    get_default_simulation_params,
    get_default_tank_params,
    load_odd_specs,
    load_tank_config,
)


class TestLoadTankConfig:
    """Test tank configuration loading."""

    def test_load_tank_config(self):
        config = load_tank_config()
        assert "tank_params" in config
        assert "simulation_defaults" in config
        assert "control_defaults" in config
        assert "supply_capacity" in config

    def test_tank_params_keys(self):
        config = load_tank_config()
        tp = config["tank_params"]
        assert "area" in tp
        assert "cd" in tp
        assert "outlet_area" in tp
        assert tp["area"] > 0
        assert 0 < tp["cd"] <= 1

    def test_control_defaults_keys(self):
        config = load_tank_config()
        cd = config["control_defaults"]
        assert "pid" in cd
        assert "mpc" in cd
        assert "kp" in cd["pid"]
        assert "horizon" in cd["mpc"]


class TestLoadOddSpecs:
    """Test ODD specification loading."""

    def test_load_odd_specs(self):
        specs = load_odd_specs()
        assert "dimensions" in specs
        assert len(specs["dimensions"]) == 6

    def test_dimension_structure(self):
        specs = load_odd_specs()
        for dim in specs["dimensions"]:
            assert "name" in dim
            assert "min_value" in dim
            assert "max_value" in dim
            assert "unit" in dim
            assert dim["max_value"] > dim["min_value"]

    def test_water_level_dimension(self):
        specs = load_odd_specs()
        wl_dims = [d for d in specs["dimensions"] if d["name"] == "water_level"]
        assert len(wl_dims) == 1
        wl = wl_dims[0]
        assert wl["unit"] == "m"
        assert wl["min_value"] == 0.1
        assert wl["max_value"] == 1.8


class TestConvenienceGetters:
    """Test convenience getter functions."""

    def test_get_default_tank_params(self):
        params = get_default_tank_params()
        assert params["area"] == 1.0
        assert params["cd"] == 0.6
        assert params["outlet_area"] == 0.01

    def test_get_default_pid_params(self):
        params = get_default_pid_params()
        assert "kp" in params
        assert "ki" in params
        assert "kd" in params
        assert params["kp"] > 0

    def test_get_default_mpc_params(self):
        params = get_default_mpc_params()
        assert "horizon" in params
        assert "q_weight" in params
        assert "r_weight" in params
        assert params["horizon"] > 0

    def test_get_default_simulation_params(self):
        params = get_default_simulation_params()
        assert "duration" in params
        assert "dt" in params
        assert "initial_h" in params
        assert "solver" in params
        assert params["dt"] > 0


class TestConfigIntegration:
    """Test that config values work with core modules."""

    def test_tank_params_work_with_simulator(self):
        from core.simulation import TankParams, run_simulation
        params = get_default_tank_params()
        tp = TankParams(**params)
        tp.validate()
        result = run_simulation(duration=10, dt=1.0, tank_params=params)
        assert len(result["water_level"]) > 0

    def test_pid_params_work_with_controller(self):
        from core.control import PIDController, PIDParams
        params = get_default_pid_params()
        pid = PIDController(PIDParams(**params))
        u = pid.compute(setpoint=1.0, measured=0.5, dt=1.0)
        assert u >= 0

    def test_odd_specs_work_with_odd_module(self):
        from core.odd import ODDSpec
        specs = load_odd_specs()
        odd = ODDSpec.from_dict(specs)
        assert len(odd.dimensions) == 6
        wl = odd.get_dimension("water_level")
        assert wl is not None
        assert wl.max_value == 1.8
