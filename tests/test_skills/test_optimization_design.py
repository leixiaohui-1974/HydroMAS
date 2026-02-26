"""Integration tests for OptimizationDesignSkill."""

import pytest
from skills.optimization_design import OptimizationDesignSkill


class TestOptimizationDesignSkill:
    @pytest.mark.asyncio
    async def test_basic_workflow(self):
        skill = OptimizationDesignSkill()
        result = await skill.run({
            "requirements": {"peak_demand": 0.02, "min_reserve_time": 300},
        })
        assert result.success
        assert "design_optimization" in result.steps_completed
        assert "simulation_verification" in result.steps_completed
        assert "sensitivity_analysis" in result.steps_completed
        assert "optimal_design" in result.data
        assert "sensitivity_analysis" in result.data
