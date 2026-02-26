"""Integration tests for MCP design server."""

import pytest
from mcp_servers.design_server import optimize_design, run_sensitivity


class TestOptimizeDesign:
    def test_basic(self):
        result = optimize_design()
        assert result["status"] in ("optimal", "fallback")
        assert result["optimal_area"] > 0

    def test_with_requirements(self):
        result = optimize_design(
            requirements={"peak_demand": 0.03, "min_reserve_time": 200},
        )
        assert result["volume"] > 0


class TestRunSensitivity:
    def test_oat(self):
        result = run_sensitivity(
            base_params={"area": 1.0, "cd": 0.6, "outlet_area": 0.01},
            param_ranges={"area": [0.5, 1.5], "cd": [0.3, 0.9]},
            method="OAT",
            n_levels=5,
        )
        assert "area" in result["parameters"]
        assert "cd" in result["parameters"]
        assert len(result["ranking"]) == 2
