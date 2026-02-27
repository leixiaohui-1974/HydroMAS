"""Tests for compute module (without Ray dependency)."""

from compute.distributed_sim import monte_carlo_sim, parameter_sweep, simulate_single


class TestDistributedSim:
    def test_simulate_single(self):
        result = simulate_single({
            "duration": 10, "dt": 1.0, "initial_h": 0.5,
        })
        assert len(result["time"]) == 11
        assert result["metadata"]["solver"] == "RK4"

    def test_parameter_sweep_local(self):
        params = [
            {"duration": 10, "dt": 1.0, "initial_h": 0.3},
            {"duration": 10, "dt": 1.0, "initial_h": 0.7},
        ]
        results = parameter_sweep(params, use_ray=False)
        assert len(results) == 2
        assert results[0]["water_level"][0] < results[1]["water_level"][0]

    def test_monte_carlo_local(self):
        base = {"duration": 10, "dt": 1.0, "initial_h": 0.5}
        vary = {"cd": (0.6, 0.05)}
        results = monte_carlo_sim(base, vary, n_samples=3, use_ray=False, seed=42)
        assert len(results) == 3
