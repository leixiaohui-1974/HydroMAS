"""Parallel data processing using Ray Data.
基于 Ray Data 的并行数据处理。

For large-scale time series data cleaning and preprocessing.
MVP: simple parallel map over chunks.
"""

from __future__ import annotations

import logging

import numpy as np
from typing import Callable

from compute.ray_config import is_ray_available, init_ray

logger = logging.getLogger(__name__)


def parallel_clean(
    data_chunks: list[list[float]],
    clean_fn: Callable[[list[float]], dict],
    use_ray: bool = True,
) -> list[dict]:
    """Clean multiple data chunks in parallel.
    并行清洗多个数据块。

    Args:
        data_chunks: List of time series chunks / 时序数据块列表
        clean_fn: Cleaning function for a single chunk / 单块清洗函数
        use_ray: Whether to use Ray / 是否使用 Ray

    Returns:
        List of cleaned results.
    """
    if use_ray and is_ray_available():
        try:
            import ray
            init_ray()

            @ray.remote
            def _remote_clean(chunk: list[float]) -> dict:
                return clean_fn(chunk)

            futures = [_remote_clean.remote(c) for c in data_chunks]
            return ray.get(futures)
        except Exception as e:
            logger.warning(f"Ray parallel clean failed, falling back to local: {e}")

    return [clean_fn(c) for c in data_chunks]


def chunk_timeseries(
    data: list[float],
    chunk_size: int = 1000,
    overlap: int = 0,
) -> list[list[float]]:
    """Split a time series into chunks for parallel processing.
    将时序分块以便并行处理。

    Args:
        data: Full time series / 完整时序
        chunk_size: Size of each chunk / 每块大小
        overlap: Overlap between chunks / 块间重叠

    Returns:
        List of chunks.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if overlap < 0:
        raise ValueError(f"overlap must be non-negative, got {overlap}")
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")

    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(data), step):
        chunk = data[i : i + chunk_size]
        if len(chunk) > 0:
            chunks.append(chunk)
    return chunks
