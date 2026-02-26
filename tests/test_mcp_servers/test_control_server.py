"""Integration tests for MCP control server."""

import pytest
from mcp_servers.control_server import run_controller


class TestRunController:
    def test_pid_single_step(self):
        result = run_controller(
            setpoint=1.0,
            current_state={"h": 0.5},
            controller_type="PID",
        )
        assert "control_output" in result
        assert result["control_output"] > 0

    def test_mpc_single_step(self):
        result = run_controller(
            setpoint=1.0,
            current_state={"h": 0.5, "q_out": 0.005},
            controller_type="MPC",
        )
        assert "control_output" in result

    def test_pid_simulation_mode(self):
        result = run_controller(
            setpoint=1.0,
            controller_type="PID",
            simulation_config={"duration": 50, "dt": 1.0, "initial_h": 0.5},
        )
        assert "water_level" in result
        assert len(result["water_level"]) == 51

    def test_mpc_simulation_mode(self):
        result = run_controller(
            setpoint=1.0,
            controller_type="MPC",
            params={"horizon": 5},
            simulation_config={"duration": 20, "dt": 1.0, "initial_h": 0.5},
        )
        assert "water_level" in result
        assert len(result["control_output"]) == 20

    def test_invalid_controller(self):
        with pytest.raises(ValueError):
            run_controller(setpoint=1.0, controller_type="RL")
