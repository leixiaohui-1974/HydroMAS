"""Tests for compute.distributed_optim module."""

import pytest
from compute.distributed_optim import parallel_sensitivity, parallel_evaluate


class TestParallelSensitivity:
    def test_oat_method(self):
        base = {"x": 1.0, "y": 2.0}
        ranges = {"x": (0.5, 1.5), "y": (1.0, 3.0)}

        def fn(p):
            return p["x"] ** 2 + p["y"]

        result = parallel_sensitivity(
            ranges, fn, method="OAT", use_ray=False,
            base_params=base, n_levels=5,
        )
        assert "x" in result["parameters"]
        assert "y" in result["parameters"]

    def test_invalid_method(self):
        with pytest.raises(ValueError):
            parallel_sensitivity({}, lambda p: 0, method="SOBOL")


class TestParallelEvaluate:
    def test_local_evaluate(self):
        params = [{"x": i} for i in range(5)]

        def fn(p):
            return p["x"] * 2

        results = parallel_evaluate(params, fn, use_ray=False)
        assert results == [0, 2, 4, 6, 8]
