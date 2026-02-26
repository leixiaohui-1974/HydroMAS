"""Tests for compute.distributed_sim module (local execution, no Ray required)."""

import pytest
from compute.distributed_sim import simulate_single, parameter_sweep, monte_carlo_sim


class TestSimulateSingle:
    def test_basic(self):
        result = simulate_single({"duration": 10, "dt": 1.0, "initial_h": 0.5})
        assert len(result["time"]) == 11

    def test_with_profile(self):
        result = simulate_single({
            "duration": 20,
            "q_in_profile": [(0, 0.01), (10, 0.03)],
            "initial_h": 0.3,
        })
        assert result["water_level"][0] == pytest.approx(0.3, abs=0.01)


class TestParameterSweep:
    def test_local_sweep(self):
        params = [
            {"duration": 10, "initial_h": h}
            for h in [0.2, 0.4, 0.6, 0.8, 1.0]
        ]
        results = parameter_sweep(params, use_ray=False)
        assert len(results) == 5
        # Initial levels should be preserved
        for i, r in enumerate(results):
            expected = [0.2, 0.4, 0.6, 0.8, 1.0][i]
            assert r["water_level"][0] == pytest.approx(expected, abs=0.01)

    def test_empty_grid(self):
        results = parameter_sweep([], use_ray=False)
        assert results == []


class TestMonteCarlo:
    def test_basic_mc(self):
        base = {"duration": 10, "dt": 1.0, "initial_h": 0.5}
        vary = {"cd": (0.6, 0.1)}
        results = monte_carlo_sim(base, vary, n_samples=5, use_ray=False, seed=42)
        assert len(results) == 5
        # Results should differ due to parameter variation
        final_levels = [r["water_level"][-1] for r in results]
        assert len(set(round(f, 6) for f in final_levels)) > 1

    def test_reproducible(self):
        base = {"duration": 10, "initial_h": 0.5}
        vary = {"cd": (0.6, 0.05)}
        r1 = monte_carlo_sim(base, vary, n_samples=3, use_ray=False, seed=123)
        r2 = monte_carlo_sim(base, vary, n_samples=3, use_ray=False, seed=123)
        assert r1[0]["water_level"] == r2[0]["water_level"]
