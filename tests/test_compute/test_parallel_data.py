"""Tests for compute.parallel_data module."""

import pytest
from compute.parallel_data import chunk_timeseries, parallel_clean


class TestChunkTimeseries:
    def test_basic_chunking(self):
        data = list(range(100))
        chunks = chunk_timeseries(data, chunk_size=30)
        assert len(chunks) == 4  # 0-29, 30-59, 60-89, 90-99

    def test_with_overlap(self):
        data = list(range(100))
        chunks = chunk_timeseries(data, chunk_size=30, overlap=10)
        assert len(chunks) == 5  # step=20, so 0,20,40,60,80

    def test_small_data(self):
        data = [1.0, 2.0]
        chunks = chunk_timeseries(data, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == data


class TestParallelClean:
    def test_local_clean(self):
        chunks = [[1.0, 2.0, 100.0, 3.0], [4.0, 5.0, -50.0, 6.0]]

        def clean_fn(chunk):
            from core.data_clean.interpolation import clean_timeseries
            return clean_timeseries(chunk, methods=["outlier_3sigma", "interpolate_linear"])

        results = parallel_clean(chunks, clean_fn, use_ray=False)
        assert len(results) == 2
        for r in results:
            assert "data" in r
