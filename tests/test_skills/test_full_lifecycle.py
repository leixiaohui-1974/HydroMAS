"""Integration tests for FullLifecycleSkill."""

import pytest

from skills.full_lifecycle import FullLifecycleSkill


class TestFullLifecycleSkill:
    @pytest.mark.asyncio
    async def test_pid_lifecycle(self):
        skill = FullLifecycleSkill()
        result = await skill.run({
            "setpoint": 1.0,
            "initial_h": 0.5,
            "controller_type": "PID",
            "duration": 100,
        })
        assert result.success
        assert len(result.steps_completed) == 6
        assert "design_optimization" in result.steps_completed
        assert "open_loop_simulation" in result.steps_completed
        assert "system_identification" in result.steps_completed
        assert "closed_loop_control" in result.steps_completed
        assert "odd_assessment" in result.steps_completed
        assert "performance_evaluation" in result.steps_completed
        # Summary
        assert "summary" in result.data
        assert result.data["summary"]["controller"] == "PID"

    @pytest.mark.asyncio
    async def test_mpc_lifecycle(self):
        skill = FullLifecycleSkill()
        result = await skill.run({
            "setpoint": 1.0,
            "controller_type": "MPC",
            "duration": 50,
        })
        assert result.success
        assert result.data["summary"]["controller"] == "MPC"
