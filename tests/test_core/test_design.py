"""Tests for core.design module."""

from core.design.sensitivity import sensitivity_morris, sensitivity_oat
from core.design.sizing import optimize_tank_size


class TestSizing:
    def test_basic_optimization(self):
        result = optimize_tank_size(
            peak_demand=0.02,
            min_reserve_time=300,
        )
        assert result["status"] in ("optimal", "fallback")
        assert result["volume"] >= 0.02 * 300 - 0.01  # meets required volume (tolerance)
        assert result["optimal_area"] > 0
        assert result["optimal_height"] > 0

    def test_cost_decreases_with_larger_space(self):
        r1 = optimize_tank_size(max_area=5.0, max_height=2.0)
        r2 = optimize_tank_size(max_area=10.0, max_height=3.0)
        # Larger design space should allow same or lower cost
        assert r2["cost"] <= r1["cost"] * 1.01  # small tolerance


class TestSensitivity:
    def test_oat_basic(self):
        base = {"x": 1.0, "y": 2.0}
        ranges = {"x": (0.5, 1.5), "y": (1.0, 3.0)}

        def eval_fn(params):
            return params["x"] ** 2 + params["y"]

        result = sensitivity_oat(base, ranges, eval_fn, n_levels=5)
        assert "x" in result["parameters"]
        assert "y" in result["parameters"]
        assert len(result["ranking"]) == 2

    def test_morris_basic(self):
        ranges = {"a": (0.5, 1.5), "b": (1.0, 3.0)}

        def eval_fn(params):
            return params["a"] * 2 + params["b"]

        result = sensitivity_morris(ranges, eval_fn, n_trajectories=5, seed=42)
        assert "a" in result["parameters"]
        assert "b" in result["parameters"]
        assert result["parameters"]["a"]["mu_star"] > 0
