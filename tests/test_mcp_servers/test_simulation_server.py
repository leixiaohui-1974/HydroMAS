"""Integration tests for MCP simulation server."""

import pytest
from mcp_servers.simulation_server import simulate_tank, simulate_batch


class TestSimulateTank:
    def test_basic_call(self):
        result = simulate_tank(duration=10, dt=1.0, initial_h=0.5)
        assert "time" in result
        assert "water_level" in result
        assert len(result["time"]) == 11

    def test_with_profile(self):
        result = simulate_tank(
            duration=20,
            dt=1.0,
            q_in_profile=[[0, 0.01], [10, 0.03]],
            initial_h=0.5,
        )
        assert len(result["water_level"]) == 21

    def test_with_tank_params(self):
        result = simulate_tank(
            duration=10,
            tank_params={"area": 2.0, "cd": 0.5},
        )
        assert result["metadata"]["solver"] == "RK4"

    def test_euler_solver(self):
        result = simulate_tank(duration=10, solver="euler")
        assert result["metadata"]["solver"] == "Euler"


class TestSimulateBatch:
    def test_batch_two_schemes(self):
        schemes = [
            {"initial_h": 0.3, "duration": 10},
            {"initial_h": 0.7, "duration": 10},
        ]
        results = simulate_batch(schemes=schemes, parallel=False)
        assert len(results) == 2
        assert results[0]["water_level"][0] < results[1]["water_level"][0]
