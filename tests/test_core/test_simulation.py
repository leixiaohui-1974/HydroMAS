"""Tests for core.simulation module.
core.simulation 模块测试。
"""

import math
import pytest
from core.simulation.tank_model import TankParams, compute_outflow, tank_ode, GRAVITY
from core.simulation.simulator import (
    run_simulation,
    simulate_euler,
    simulate_rk4,
    _interpolate_inflow,
)


class TestTankParams:
    def test_default_params(self):
        p = TankParams()
        assert p.area == 1.0
        assert p.cd == 0.6
        assert p.outlet_area == 0.01

    def test_validate_good(self):
        p = TankParams(area=2.0, cd=0.5, outlet_area=0.02)
        p.validate()  # should not raise

    def test_validate_bad_area(self):
        p = TankParams(area=-1.0)
        with pytest.raises(ValueError, match="area"):
            p.validate()

    def test_validate_bad_cd(self):
        p = TankParams(cd=1.5)
        with pytest.raises(ValueError, match="coefficient"):
            p.validate()

    def test_validate_bad_outlet(self):
        p = TankParams(outlet_area=0.0)
        with pytest.raises(ValueError, match="Outlet"):
            p.validate()


class TestComputeOutflow:
    def test_zero_level(self):
        p = TankParams()
        assert compute_outflow(0.0, p) == 0.0

    def test_negative_level(self):
        p = TankParams()
        assert compute_outflow(-0.5, p) == 0.0

    def test_positive_level(self):
        p = TankParams(cd=0.6, outlet_area=0.01)
        h = 1.0
        expected = 0.6 * 0.01 * math.sqrt(2 * GRAVITY * 1.0)
        assert abs(compute_outflow(h, p) - expected) < 1e-10

    def test_outflow_increases_with_level(self):
        p = TankParams()
        q1 = compute_outflow(0.5, p)
        q2 = compute_outflow(1.0, p)
        assert q2 > q1


class TestTankODE:
    def test_steady_state(self):
        p = TankParams()
        h = 1.0
        q_in = compute_outflow(h, p)
        dhdt = tank_ode(h, q_in, p)
        assert abs(dhdt) < 1e-10

    def test_filling(self):
        p = TankParams()
        dhdt = tank_ode(0.5, 0.1, p)
        assert dhdt > 0  # large inflow should fill the tank

    def test_draining(self):
        p = TankParams()
        dhdt = tank_ode(1.0, 0.0, p)
        assert dhdt < 0  # zero inflow should drain the tank


class TestInterpolateInflow:
    def test_empty_profile(self):
        assert _interpolate_inflow(5.0, []) == 0.0

    def test_single_point(self):
        assert _interpolate_inflow(5.0, [(0.0, 0.01)]) == 0.01

    def test_before_first(self):
        profile = [(10.0, 0.01), (20.0, 0.02)]
        assert _interpolate_inflow(5.0, profile) == 0.01

    def test_after_last(self):
        profile = [(10.0, 0.01), (20.0, 0.02)]
        assert _interpolate_inflow(25.0, profile) == 0.02

    def test_midpoint(self):
        profile = [(0.0, 0.0), (10.0, 0.1)]
        val = _interpolate_inflow(5.0, profile)
        assert abs(val - 0.05) < 1e-10


class TestSimulators:
    def test_euler_basic(self):
        p = TankParams()
        result = simulate_euler(10.0, 1.0, [(0, 0.01)], 0.5, p)
        assert len(result["time"]) == 11
        assert len(result["water_level"]) == 11
        assert result["metadata"]["solver"] == "Euler"

    def test_rk4_basic(self):
        p = TankParams()
        result = simulate_rk4(10.0, 1.0, [(0, 0.01)], 0.5, p)
        assert len(result["time"]) == 11
        assert result["metadata"]["solver"] == "RK4"

    def test_run_simulation_euler(self):
        result = run_simulation(10.0, dt=1.0, solver="euler")
        assert result["metadata"]["solver"] == "Euler"

    def test_run_simulation_rk4(self):
        result = run_simulation(10.0, dt=1.0, solver="rk4")
        assert result["metadata"]["solver"] == "RK4"

    def test_unknown_solver(self):
        with pytest.raises(ValueError, match="Unknown solver"):
            run_simulation(10.0, solver="adams")

    def test_level_bounded(self):
        # Large inflow should not exceed h_max
        result = run_simulation(
            100.0, dt=1.0,
            q_in_profile=[(0, 0.5)],
            initial_h=1.9,
            tank_params={"h_max": 2.0},
        )
        assert max(result["water_level"]) <= 2.0

    def test_level_non_negative(self):
        # Zero inflow should not go below h_min
        result = run_simulation(
            100.0, dt=1.0,
            q_in_profile=[(0, 0.0)],
            initial_h=0.01,
        )
        assert min(result["water_level"]) >= 0.0

    def test_step_response(self):
        """Test that step increase in inflow raises water level."""
        result = run_simulation(
            100.0, dt=1.0,
            q_in_profile=[(0, 0.001), (10, 0.05)],
            initial_h=0.5,
        )
        assert result["water_level"][-1] > result["water_level"][0]
