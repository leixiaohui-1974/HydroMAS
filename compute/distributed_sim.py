"""Distributed simulation using Ray for parameter sweeps and Monte Carlo.
基于 Ray 的分布式仿真 — 参数扫描与蒙特卡洛。

Wraps core.simulation functions as Ray remote tasks for parallel execution.
"""

from __future__ import annotations

import logging
from typing import Any

from core.simulation.simulator import run_simulation
from compute.ray_config import is_ray_available, init_ray

logger = logging.getLogger(__name__)


def _simulate_local(params: dict) -> dict:
    """Run simulation locally (fallback when Ray unavailable).
    本地运行仿真（Ray 不可用时的回退方案）。
    """
    return run_simulation(**params)


def simulate_single(params: dict) -> dict:
    """Run a single simulation, using Ray if available.
    运行单次仿真，可用时使用 Ray。
    """
    return run_simulation(**params)


def parameter_sweep(param_grid: list[dict], use_ray: bool = True) -> list[dict]:
    """Run parameter sweep in parallel using Ray (or locally as fallback).
    使用 Ray 并行运行参数扫描（不可用时本地运行）。

    Args:
        param_grid: List of parameter dicts, each passed to run_simulation / 参数网格
        use_ray: Whether to attempt using Ray / 是否使用 Ray

    Returns:
        List of simulation results.
    """
    if use_ray and is_ray_available():
        try:
            import ray
            init_ray()

            @ray.remote
            def _remote_sim(p: dict) -> dict:
                from core.simulation.simulator import run_simulation
                return run_simulation(**p)

            futures = [_remote_sim.remote(p) for p in param_grid]
            return ray.get(futures)
        except Exception as e:
            logger.warning(f"Ray parameter sweep failed, falling back to local: {e}")

    # Local fallback
    return [run_simulation(**p) for p in param_grid]


def monte_carlo_sim(
    base_params: dict,
    vary_params: dict[str, tuple[float, float]],
    n_samples: int = 100,
    use_ray: bool = True,
    seed: int | None = None,
) -> list[dict]:
    """Run Monte Carlo simulation with parameter uncertainty.
    带参数不确定性的蒙特卡洛仿真。

    Args:
        base_params: Base simulation parameters / 基准仿真参数
        vary_params: {param_path: (mean, std)} for Gaussian sampling / 变异参数
        n_samples: Number of Monte Carlo samples / 蒙特卡洛样本数
        use_ray: Whether to use Ray / 是否使用 Ray
        seed: Random seed / 随机种子

    Returns:
        List of simulation results for each sample.
    """
    if n_samples <= 0:
        raise ValueError(f"n_samples must be positive, got {n_samples}")

    for param_name, (mean, std) in vary_params.items():
        if std < 0:
            raise ValueError(
                f"Standard deviation for '{param_name}' must be non-negative, got {std}"
            )

    import numpy as np
    rng = np.random.default_rng(seed)

    param_grid = []
    for _ in range(n_samples):
        params = dict(base_params)
        tank_params = dict(params.get("tank_params", {}) or {})

        for param_name, (mean, std) in vary_params.items():
            value = float(rng.normal(mean, std))
            # Clamp to positive — physical tank params must be > 0
            tank_params[param_name] = max(1e-9, value)

        params["tank_params"] = tank_params
        param_grid.append(params)

    return parameter_sweep(param_grid, use_ray=use_ray)
