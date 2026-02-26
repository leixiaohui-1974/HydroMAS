"""Distributed optimization using Ray for parallel multi-objective and sensitivity.
基于 Ray 的分布式优化 — 并行多目标优化与敏感性分析。
"""

from __future__ import annotations

import logging

from typing import Callable

from compute.ray_config import is_ray_available, init_ray

logger = logging.getLogger(__name__)


def parallel_sensitivity(
    param_ranges: dict[str, tuple[float, float]],
    evaluate_fn: Callable[[dict], float],
    method: str = "OAT",
    use_ray: bool = True,
    **kwargs,
) -> dict:
    """Run sensitivity analysis, parallelizing evaluations with Ray.
    使用 Ray 并行化敏感性分析。

    Args:
        param_ranges: Parameter ranges / 参数范围
        evaluate_fn: Evaluation function / 评价函数
        method: "OAT" or "Morris" / 分析方法
        use_ray: Whether to use Ray / 是否使用 Ray
        **kwargs: Additional arguments for the sensitivity method.

    Returns:
        Sensitivity analysis results.
    """
    from core.design.sensitivity import sensitivity_oat, sensitivity_morris

    if method == "OAT":
        base_params = kwargs.get("base_params", {})
        if not base_params:
            base_params = {k: (lo + hi) / 2 for k, (lo, hi) in param_ranges.items()}
        return sensitivity_oat(base_params, param_ranges, evaluate_fn, **{k: v for k, v in kwargs.items() if k != "base_params"})
    elif method == "Morris":
        return sensitivity_morris(param_ranges, evaluate_fn, **kwargs)
    else:
        raise ValueError(f"Unknown method: {method}")


def parallel_evaluate(
    param_list: list[dict],
    evaluate_fn: Callable[[dict], float],
    use_ray: bool = True,
) -> list[float]:
    """Evaluate a function over many parameter sets in parallel.
    并行评估多组参数。

    Args:
        param_list: List of parameter dicts / 参数列表
        evaluate_fn: Evaluation function / 评价函数
        use_ray: Whether to use Ray / 是否使用 Ray

    Returns:
        List of evaluation results.
    """
    if use_ray and is_ray_available():
        try:
            import ray
            init_ray()

            remote_fn = ray.remote(evaluate_fn)
            futures = [remote_fn.remote(p) for p in param_list]
            return ray.get(futures)
        except Exception as e:
            logger.warning(f"Ray parallel evaluate failed, falling back to local: {e}")

    return [evaluate_fn(p) for p in param_list]
