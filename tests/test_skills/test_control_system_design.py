"""Integration tests for ControlSystemDesignSkill."""

import pytest

from skills.control_system_design import ControlSystemDesignSkill


class TestControlSystemDesignSkill:
    @pytest.mark.asyncio
    async def test_pid_workflow(self):
        skill = ControlSystemDesignSkill()
        result = await skill.run({
            "controller_type": "PID",
            "setpoint": 1.0,
            "initial_h": 0.5,
            "duration": 100,
        })
        assert result.success
        assert "open_loop_simulation" in result.steps_completed
        assert "system_identification" in result.steps_completed
        assert "closed_loop_control" in result.steps_completed
        assert "performance_evaluation" in result.steps_completed
        assert "performance_metrics" in result.data

    @pytest.mark.asyncio
    async def test_mpc_workflow(self):
        skill = ControlSystemDesignSkill()
        result = await skill.run({
            "controller_type": "MPC",
            "setpoint": 1.0,
            "initial_h": 0.5,
            "duration": 50,
        })
        assert result.success
        assert len(result.steps_completed) == 4
