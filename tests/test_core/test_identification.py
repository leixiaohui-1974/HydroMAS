"""Tests for core.identification module."""

import math
import pytest
import numpy as np

from core.identification.least_squares import identify_tank_params
from core.identification.arx_model import identify_arx, predict_arx
from core.simulation.tank_model import TankParams, compute_outflow, GRAVITY


class TestLeastSquares:
    def test_identify_known_params(self):
        """Identify known Cd and outlet_area from synthetic data."""
        true_cd = 0.6
        true_a = 0.01

        h_arr = np.linspace(0.2, 1.5, 50)
        q_out = true_cd * true_a * np.sqrt(2 * GRAVITY * h_arr)
        # Add small noise
        q_out += np.random.default_rng(42).normal(0, 1e-5, len(q_out))

        result = identify_tank_params(h_arr.tolist(), q_out.tolist())
        assert result["converged"]
        assert abs(result["cd"] - true_cd) < 0.05
        assert abs(result["outlet_area"] - true_a) < 0.005
        assert result["r_squared"] > 0.99

    def test_short_data(self):
        with pytest.raises(ValueError, match="at least 2"):
            identify_tank_params([1.0], [0.01])

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            identify_tank_params([1.0, 2.0], [0.01])


class TestARX:
    def test_identify_simple(self):
        """Test ARX identification on simple linear data."""
        n = 100
        u = np.ones(n) * 0.01
        y = np.zeros(n)
        for i in range(1, n):
            y[i] = 0.95 * y[i - 1] + 0.3 * u[i - 1] + np.random.default_rng(42).normal(0, 0.001)

        result = identify_arx(y.tolist(), u.tolist(), na=1, nb=1, nk=1)
        assert result["r_squared"] > 0.9
        assert len(result["a_coefficients"]) == 1
        assert len(result["b_coefficients"]) == 1

    def test_predict_arx(self):
        model = {
            "a_coefficients": [-0.9],
            "b_coefficients": [0.3],
            "na": 1, "nb": 1, "nk": 1,
        }
        y_history = [0.5, 0.6, 0.7]
        u_future = [0.01] * 5
        pred = predict_arx(model, y_history, u_future)
        assert len(pred) == 5

    def test_insufficient_data(self):
        with pytest.raises(ValueError):
            identify_arx([1.0, 2.0], [0.01, 0.02], na=3, nb=3)
