"""Integration tests for MCP scheduling server."""

import pytest
from mcp_servers.scheduling_server import optimize_schedule


class TestOptimizeSchedule:
    def test_rule_based(self):
        result = optimize_schedule(
            demand_forecast=[0.01, 0.02, 0.015],
            method="rule",
            constraints={"current_level": 0.5, "target_level": 1.0},
        )
        assert "inflow_rate" in result
        assert result["rule"] is not None

    def test_lp_method(self, sample_demand_forecast):
        result = optimize_schedule(
            demand_forecast=sample_demand_forecast,
            supply_capacity=0.05,
            method="lp",
        )
        # Either optimal or fallback (if PuLP missing)
        assert result["status"] in ("optimal", "fallback", "infeasible")

    def test_invalid_method(self):
        with pytest.raises(ValueError):
            optimize_schedule(demand_forecast=[0.01], method="genetic")
