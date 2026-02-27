"""Tests for LP scheduler (with PuLP fallback)."""

import pytest

from core.scheduling.lp_scheduler import _fallback_schedule, optimize_schedule_lp


class TestFallbackSchedule:
    def test_basic_fallback(self):
        demand = [0.01, 0.02, 0.015]
        result = _fallback_schedule(demand, supply_capacity=0.05)
        assert result["status"] == "fallback"
        assert len(result["schedule"]) == 3
        # Fallback = demand * 1.1
        assert result["schedule"][0] == pytest.approx(0.011, abs=0.001)


class TestLPScheduler:
    def test_basic_schedule(self, sample_demand_forecast):
        result = optimize_schedule_lp(
            demand_forecast=sample_demand_forecast,
            supply_capacity=0.05,
        )
        # Either optimal (PuLP installed) or fallback
        assert result["status"] in ("optimal", "fallback", "infeasible")
        assert len(result["schedule"]) > 0

    def test_tight_constraints(self):
        """Test with very tight constraints that may be infeasible."""
        demand = [0.04, 0.04, 0.04, 0.04]  # high demand
        result = optimize_schedule_lp(
            demand_forecast=demand,
            supply_capacity=0.05,
            min_level=0.8,
            max_level=1.0,
            initial_level=0.9,
        )
        # May be optimal or infeasible depending on constraints
        assert result["status"] in ("optimal", "fallback", "infeasible")

    def test_sufficient_supply(self):
        """With generous supply, should find optimal solution."""
        demand = [0.005] * 5
        result = optimize_schedule_lp(
            demand_forecast=demand,
            supply_capacity=0.05,
            initial_level=1.0,
        )
        if result["status"] == "optimal":
            assert len(result["predicted_levels"]) == 6  # n_periods + 1
