"""Integration tests for ReuseSchedulingSkill (回用调度)."""

import pytest

from skills.reuse_scheduling import ReuseSchedulingSkill

# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

def _source_quality():
    return {"cod": 30.0, "turbidity": 5.0, "ph": 7.2, "conductivity": 800.0}


def _target_requirements():
    return [
        {"workshop_id": "ws_cooling", "max_cod": 50.0, "max_turbidity": 10.0, "demand_m3d": 200.0},
        {"workshop_id": "ws_washing", "max_cod": 80.0, "max_turbidity": 20.0, "demand_m3d": 150.0},
    ]


def _sources():
    return [
        {"source_id": "src_reclaim", "capacity_m3d": 300.0, "cod": 30.0, "turbidity": 5.0},
    ]


def _demands():
    return [
        {"workshop_id": "ws_cooling", "demand_m3d": 200.0, "max_cod": 50.0, "max_turbidity": 10.0},
        {"workshop_id": "ws_washing", "demand_m3d": 150.0, "max_cod": 80.0, "max_turbidity": 20.0},
    ]


# ---------------------------------------------------------------------------
# Mock tool functions
# ---------------------------------------------------------------------------

def _mock_match_reuse_path(source_quality, target_requirements):
    return {
        "matched_paths": [
            {
                "workshop_id": "ws_cooling",
                "demand_m3d": 200.0,
                "quality_margin": {
                    "cod_margin": 20.0,
                    "turbidity_margin": 5.0,
                },
            },
            {
                "workshop_id": "ws_washing",
                "demand_m3d": 150.0,
                "quality_margin": {
                    "cod_margin": 50.0,
                    "turbidity_margin": 15.0,
                },
            },
        ],
        "unmatched": [],
        "n_matched": 2,
        "n_unmatched": 0,
        "source_quality": source_quality,
        "paths": [
            {"source": "src_reclaim", "target": "ws_cooling"},
            {"source": "src_reclaim", "target": "ws_washing"},
        ],
        "matched_sources": [
            {"source_id": "src_reclaim", "capacity_m3d": 300.0, "cod": 30.0, "turbidity": 5.0},
        ],
        "matched_demands": [
            {
                "workshop_id": "ws_cooling",
                "demand_m3d": 200.0,
                "max_cod": 50.0, "max_turbidity": 10.0,
            },
            {
                "workshop_id": "ws_washing",
                "demand_m3d": 150.0,
                "max_cod": 80.0, "max_turbidity": 20.0,
            },
        ],
    }


def _mock_optimize_reuse_schedule(sources, demands, match_paths):
    total_reuse = 300.0
    total_demand = 350.0
    return {
        "status": "Optimal",
        "method": "pulp_lp",
        "schedule": [
            {"source_id": "src_reclaim", "target_id": "ws_cooling", "volume_m3d": 200.0},
            {"source_id": "src_reclaim", "target_id": "ws_washing", "volume_m3d": 100.0},
        ],
        "total_reuse_m3d": total_reuse,
        "total_demand_m3d": total_demand,
        "reuse_rate": round(total_reuse / total_demand, 4),
    }


def _mock_evaluate_reuse_benefit(schedule, current_reuse_rate):
    return {
        "new_reuse_rate": 0.8571,
        "current_reuse_rate": current_reuse_rate,
        "improvement": 0.8571 - current_reuse_rate,
        "water_saved_m3_per_day": 150.0,
        "cost_saved_per_day": 600.0,
        "daily_savings_m3": 150.0,
        "annual_savings_m3": 54750.0,
    }


def _build_skill():
    """Create a ReuseSchedulingSkill with all tools mocked."""
    skill = ReuseSchedulingSkill()
    skill.register_tool("match_reuse_path", _mock_match_reuse_path)
    skill.register_tool("optimize_reuse_schedule", _mock_optimize_reuse_schedule)
    skill.register_tool("evaluate_reuse_benefit", _mock_evaluate_reuse_benefit)
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReuseScheduling:
    @pytest.mark.asyncio
    async def test_reuse_scheduling_init(self):
        """ReuseSchedulingSkill can be instantiated and has an execute method."""
        skill = ReuseSchedulingSkill()
        assert hasattr(skill, "execute")
        assert callable(skill.execute)

    @pytest.mark.asyncio
    async def test_reuse_scheduling_execute(self):
        """Full execution with source_quality and target_requirements returns success."""
        skill = _build_skill()
        result = await skill.run({
            "source_quality": _source_quality(),
            "target_requirements": _target_requirements(),
            "sources": _sources(),
            "demands": _demands(),
            "current_reuse_rate": 0.3,
        })
        assert result.success
        assert "matching" in result.data
        assert "schedule" in result.data
        assert "benefit" in result.data
        assert "improvement" in result.data

    @pytest.mark.asyncio
    async def test_reuse_scheduling_missing_params(self):
        """Missing source_quality and target_requirements returns error."""
        skill = _build_skill()
        result = await skill.run({})
        assert not result.success
        assert "source_quality" in result.error or "target_requirements" in result.error

    @pytest.mark.asyncio
    async def test_reuse_scheduling_steps(self):
        """Verify steps_completed for a complete run."""
        skill = _build_skill()
        result = await skill.run({
            "source_quality": _source_quality(),
            "target_requirements": _target_requirements(),
            "current_reuse_rate": 0.3,
        })
        assert result.success
        assert result.steps_completed == [
            "quality_matching",
            "schedule_optimization",
            "benefit_evaluation",
        ]

    @pytest.mark.asyncio
    async def test_reuse_scheduling_improvement_summary(self):
        """Improvement dict contains expected keys and realistic values."""
        skill = _build_skill()
        result = await skill.run({
            "source_quality": _source_quality(),
            "target_requirements": _target_requirements(),
            "current_reuse_rate": 0.3,
        })
        assert result.success
        improvement = result.data["improvement"]
        assert "reuse_rate_before" in improvement
        assert "reuse_rate_after" in improvement
        assert "reuse_rate_improvement" in improvement
        assert "water_saved_m3_per_day" in improvement
        assert "summary" in improvement
        assert improvement["reuse_rate_before"] == 0.3

    @pytest.mark.asyncio
    async def test_reuse_scheduling_zero_baseline(self):
        """Starting from zero reuse rate still works correctly."""
        skill = _build_skill()
        result = await skill.run({
            "source_quality": _source_quality(),
            "target_requirements": _target_requirements(),
            "current_reuse_rate": 0.0,
        })
        assert result.success
        improvement = result.data["improvement"]
        assert improvement["reuse_rate_before"] == 0.0
        assert improvement["reuse_rate_after"] > 0.0

    @pytest.mark.asyncio
    async def test_reuse_scheduling_execution_time(self):
        """Execution time is recorded and positive."""
        skill = _build_skill()
        result = await skill.run({
            "source_quality": _source_quality(),
            "target_requirements": _target_requirements(),
        })
        assert result.success
        assert result.execution_time > 0
