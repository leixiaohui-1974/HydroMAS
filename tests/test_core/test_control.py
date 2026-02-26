"""Tests for core.control module."""

import pytest
from core.control.pid_controller import PIDController, PIDParams, run_pid_control
from core.control.mpc_controller import MPCController, run_mpc_control


class TestPIDController:
    def test_basic_output(self):
        pid = PIDController(PIDParams(kp=2.0, ki=0.1, kd=0.05))
        u = pid.compute(setpoint=1.0, measured=0.5, dt=1.0)
        assert u > 0  # should try to increase level

    def test_clamping(self):
        pid = PIDController(PIDParams(kp=100.0, output_max=0.05))
        u = pid.compute(setpoint=1.0, measured=0.0)
        assert u == 0.05  # clamped to max

    def test_reset(self):
        pid = PIDController()
        pid.compute(1.0, 0.5)
        pid.reset()
        assert len(pid.get_history()) == 0

    def test_history_tracking(self):
        pid = PIDController()
        pid.compute(1.0, 0.5)
        pid.compute(1.0, 0.6)
        assert len(pid.get_history()) == 2


class TestRunPIDControl:
    def test_basic_run(self):
        result = run_pid_control(
            setpoint=1.0,
            initial_h=0.5,
            duration=50,
            dt=1.0,
        )
        assert len(result["time"]) == 51
        assert len(result["water_level"]) == 51
        assert len(result["control_output"]) == 50

    def test_approaches_setpoint(self):
        result = run_pid_control(
            setpoint=1.0,
            initial_h=0.5,
            duration=200,
            dt=1.0,
            pid_params={"kp": 2.0, "ki": 0.1, "kd": 0.05},
        )
        final_h = result["water_level"][-1]
        assert abs(final_h - 1.0) < 0.3  # should approach setpoint


class TestMPCController:
    def test_basic_compute(self):
        mpc = MPCController(horizon=5, u_max=0.05)
        u = mpc.compute(current_h=0.5, setpoint=1.0, q_out_estimate=0.005)
        assert 0.0 <= u <= 0.05

    def test_history(self):
        mpc = MPCController(horizon=5)
        mpc.compute(0.5, 1.0)
        mpc.compute(0.6, 1.0)
        assert len(mpc.get_history()) == 2

    def test_reset(self):
        mpc = MPCController()
        mpc.compute(0.5, 1.0)
        mpc.reset()
        assert len(mpc.get_history()) == 0


class TestRunMPCControl:
    def test_basic_run(self):
        result = run_mpc_control(
            setpoint=1.0,
            initial_h=0.5,
            duration=20,
            dt=1.0,
            mpc_params={"horizon": 5},
        )
        assert len(result["time"]) == 21
        assert len(result["control_output"]) == 20
