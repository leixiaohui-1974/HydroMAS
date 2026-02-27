"""Tests for core.prediction module."""

import numpy as np
import pytest

from core.prediction.linear_predictor import predict_linear, predict_polynomial


class TestLinearPredictor:
    def test_basic_prediction(self):
        data = list(range(100))  # linear trend
        result = predict_linear(data, horizon=10)
        assert len(result["predictions"]) == 10
        assert result["slope"] > 0

    def test_confidence_intervals(self):
        data = [float(i) for i in range(50)]
        result = predict_linear(data, horizon=5)
        assert len(result["confidence_upper"]) == 5
        assert len(result["confidence_lower"]) == 5
        for u, lower in zip(result["confidence_upper"], result["confidence_lower"]):
            assert u >= lower

    def test_lookback(self):
        data = list(range(100))
        result = predict_linear(data, horizon=5, lookback=10)
        assert result["method"] == "linear"

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 2"):
            predict_linear([1.0], horizon=5)


class TestPolynomialPredictor:
    def test_quadratic(self):
        x = np.arange(50)
        data = (x ** 2 + 2 * x + 1).tolist()
        result = predict_polynomial(data, horizon=5, degree=2)
        assert len(result["predictions"]) == 5
        assert len(result["coefficients"]) == 3  # degree 2 = 3 coefficients

    def test_insufficient_points(self):
        with pytest.raises(ValueError):
            predict_polynomial([1.0, 2.0], horizon=5, degree=3)
