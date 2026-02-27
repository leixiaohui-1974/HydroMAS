"""Tests for core.data_clean module."""

import math

import pytest

from core.data_clean.interpolation import (
    clean_timeseries,
    interpolate_linear,
    interpolate_spline,
    median_filter,
)
from core.data_clean.outlier_detect import detect_3sigma, detect_iqr, detect_mad


class TestOutlierDetection:
    def test_3sigma_no_outliers(self):
        data = [1.0, 1.1, 0.9, 1.05, 0.95] * 10
        result = detect_3sigma(data)
        assert result["n_outliers"] == 0

    def test_3sigma_with_outlier(self):
        data = [1.0] * 50 + [100.0]
        result = detect_3sigma(data)
        assert result["n_outliers"] >= 1
        assert 50 in result["outlier_indices"]

    def test_iqr_with_outlier(self):
        data = [1.0, 1.1, 0.9, 1.05, 0.95, 10.0]
        result = detect_iqr(data)
        assert result["n_outliers"] >= 1

    def test_mad_no_outliers(self):
        data = [1.0, 1.1, 0.9, 1.05, 0.95] * 10
        result = detect_mad(data)
        assert result["n_outliers"] == 0

    def test_constant_data(self):
        data = [5.0] * 20
        result = detect_3sigma(data)
        assert result["n_outliers"] == 0


class TestInterpolation:
    def test_linear_no_missing(self):
        data = [1.0, 2.0, 3.0, 4.0]
        result = interpolate_linear(data)
        assert result["n_filled"] == 0
        assert result["data"] == data

    def test_linear_with_nan(self):
        data = [1.0, float("nan"), 3.0, 4.0]
        result = interpolate_linear(data)
        assert result["n_filled"] == 1
        assert abs(result["data"][1] - 2.0) < 0.01

    def test_spline_with_nan(self):
        data = [1.0, float("nan"), 3.0, 4.0, 5.0, 6.0]
        result = interpolate_spline(data)
        assert result["n_filled"] == 1

    def test_median_filter(self):
        data = [1.0, 1.0, 100.0, 1.0, 1.0]
        result = median_filter(data, window_size=3)
        assert result["data"][2] == 1.0  # outlier replaced by median

    def test_median_filter_even_window(self):
        data = [1.0, 2.0, 3.0, 4.0]
        result = median_filter(data, window_size=4)
        assert result["window_size"] == 5  # rounded up to odd


class TestCleanTimeseries:
    def test_default_pipeline(self):
        data = [1.0, 1.1, 100.0, float("nan"), 1.05, 0.95]
        result = clean_timeseries(data)
        assert len(result["data"]) == 6
        assert not any(math.isnan(v) for v in result["data"])

    def test_custom_pipeline(self):
        data = [1.0, 100.0, 1.0, float("nan"), 1.0]
        result = clean_timeseries(data, methods=["outlier_iqr", "interpolate_linear"])
        assert len(result["steps"]) == 2

    def test_unknown_method(self):
        with pytest.raises(ValueError, match="Unknown"):
            clean_timeseries([1.0], methods=["nonexistent"])
