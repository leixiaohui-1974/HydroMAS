"""Integration tests for MCP data cleaning server."""

import math
import pytest
from mcp_servers.dataclean_server import clean_timeseries, detect_outliers


class TestCleanTimeseries:
    def test_basic_clean(self, sample_noisy_series):
        result = clean_timeseries(
            raw_data=sample_noisy_series,
            methods=["outlier_3sigma", "interpolate_linear"],
        )
        assert len(result["data"]) == len(sample_noisy_series)
        assert not any(math.isnan(v) for v in result["data"])
        assert len(result["steps"]) == 2


class TestDetectOutliers:
    def test_3sigma(self):
        data = [1.0] * 50 + [100.0]
        result = detect_outliers(data, method="3sigma")
        assert result["n_outliers"] >= 1

    def test_iqr(self):
        data = [1.0, 1.1, 0.9, 1.05, 10.0]
        result = detect_outliers(data, method="iqr")
        assert result["n_outliers"] >= 1

    def test_mad(self):
        data = [1.0] * 50 + [100.0]
        result = detect_outliers(data, method="mad")
        assert result["n_outliers"] >= 1

    def test_invalid_method(self):
        with pytest.raises(ValueError):
            detect_outliers([1.0], method="invalid")
