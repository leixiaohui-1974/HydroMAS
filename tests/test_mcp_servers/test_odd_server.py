"""Integration tests for MCP ODD server."""

import pytest
from mcp_servers.odd_server import check_odd, get_mrc_plan


class TestCheckODD:
    def test_normal_state(self):
        result = check_odd(current_state={"water_level": 1.0})
        assert result["zone"] == "normal"

    def test_mrc_state(self):
        result = check_odd(current_state={"water_level": 2.5})
        assert result["zone"] == "mrc"

    def test_predictive_mode(self):
        states = [
            {"water_level": 1.0},
            {"water_level": 1.5},
            {"water_level": 2.0},
        ]
        result = check_odd(
            current_state=states[0],
            check_mode="predictive",
            forecast_series=states,
            time_series=[0.0, 1.0, 2.0],
        )
        assert result["worst_zone"] == "mrc"
        assert result["time_to_breach"] == 2.0


class TestGetMRCPlan:
    def test_basic_plan(self):
        violations = [
            {"dimension": "water_level", "bound_violated": "upper", "value": 2.0, "limit": 1.8}
        ]
        result = get_mrc_plan(violations=violations, current_state={"water_level": 2.0})
        assert result["status"] == "mrc_activated"
        assert len(result["actions"]) >= 1
