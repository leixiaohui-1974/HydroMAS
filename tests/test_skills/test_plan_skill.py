"""Integration tests for PlanSkill (四预: 预案)."""

import pytest
from skills.plan_skill import PlanSkill


class TestPlanSkill:
    @pytest.mark.asyncio
    async def test_with_inline_rehearsal(self):
        """Test plan generation with inline rehearsal."""
        skill = PlanSkill()
        result = await skill.run({"duration": 100})
        assert result.success
        assert "inline_rehearsal" in result.steps_completed
        assert "schedule_optimization" in result.steps_completed
        assert "safety_verification" in result.steps_completed
        assert "plan_document_generation" in result.steps_completed
        plan = result.data["plan"]
        assert "title" in plan
        assert "dispatch_commands" in plan
        assert "safety_verification" in plan
        assert "non_engineering_measures" in plan

    @pytest.mark.asyncio
    async def test_with_provided_rehearsal(self):
        """Test plan with pre-computed rehearsal results."""
        from core.simulation.simulator import run_simulation
        sim = run_simulation(duration=100, initial_h=0.5)
        rehearsal = {
            "ranking": [{"scheme_index": 0, "label": "Test"}],
            "sim_results": [sim],
            "schemes": [{"label": "Test"}],
        }
        skill = PlanSkill()
        result = await skill.run({"rehearsal": rehearsal})
        assert result.success
        assert "best_scheme_selection" in result.steps_completed

    @pytest.mark.asyncio
    async def test_plan_safety_check(self):
        """Plan should include safety verification."""
        skill = PlanSkill()
        result = await skill.run({})
        assert result.success
        sc = result.data["safety_check"]
        assert "zone" in sc
