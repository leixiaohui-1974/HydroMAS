"""Sensitivity analysis for water system parameters.
水系统参数敏感性分析。

Methods:
    - One-At-a-Time (OAT) / 单因素分析
    - Morris method (elementary effects) / Morris 方法
"""

from __future__ import annotations

from typing import Callable

import numpy as np


def sensitivity_oat(
    base_params: dict[str, float],
    param_ranges: dict[str, tuple[float, float]],
    evaluate_fn: Callable[[dict], float],
    n_levels: int = 10,
) -> dict:
    """One-At-a-Time sensitivity analysis.
    单因素敏感性分析。

    Varies each parameter independently while keeping others at base values.

    Args:
        base_params: Baseline parameter values / 基准参数值
        param_ranges: {param_name: (min, max)} ranges / 参数范围
        evaluate_fn: Function that takes params dict and returns scalar metric / 评价函数
        n_levels: Number of levels per parameter / 每个参数的水平数

    Returns:
        Dict with sensitivity indices and detailed sweep results.
    """
    if n_levels < 2:
        raise ValueError(f"n_levels must be at least 2, got {n_levels}")
    base_output = evaluate_fn(base_params)
    results = {}

    for param_name, (p_min, p_max) in param_ranges.items():
        levels = np.linspace(p_min, p_max, n_levels)
        outputs = []

        for val in levels:
            test_params = dict(base_params)
            test_params[param_name] = float(val)
            out = evaluate_fn(test_params)
            outputs.append(out)

        outputs = np.array(outputs, dtype=float)
        # Filter NaN values from failed evaluations
        valid = outputs[~np.isnan(outputs)]
        if len(valid) == 0:
            # All evaluations returned NaN — cannot compute sensitivity
            results[param_name] = {
                "levels": levels.tolist(),
                "outputs": outputs.tolist(),
                "sensitivity_index": 0.0,
                "output_range": 0.0,
                "base_value": base_params[param_name],
                "base_output": base_output,
                "all_nan": True,
            }
            continue
        # Sensitivity index: (output_range / param_range) / base_output (normalized)
        output_range = float(np.max(valid) - np.min(valid))
        param_range = p_max - p_min
        if not np.isclose(base_output, 0.0) and not np.isclose(param_range, 0.0):
            sensitivity = (output_range / param_range) / abs(base_output)
        elif not np.isclose(param_range, 0.0):
            sensitivity = output_range / param_range
        else:
            sensitivity = output_range

        results[param_name] = {
            "levels": levels.tolist(),
            "outputs": outputs.tolist(),
            "sensitivity_index": float(sensitivity),
            "output_range": output_range,
            "base_value": base_params[param_name],
            "base_output": base_output,
        }

    # Rank parameters by sensitivity
    ranking = sorted(results.keys(), key=lambda k: results[k]["sensitivity_index"], reverse=True)

    return {
        "method": "OAT",
        "parameters": results,
        "ranking": ranking,
        "base_output": base_output,
    }


def sensitivity_morris(
    param_ranges: dict[str, tuple[float, float]],
    evaluate_fn: Callable[[dict], float],
    n_trajectories: int = 10,
    n_levels: int = 4,
    seed: int | None = None,
) -> dict:
    """Morris method (elementary effects) sensitivity analysis.
    Morris 方法（基本效应）敏感性分析。

    Args:
        param_ranges: {param_name: (min, max)} / 参数范围
        evaluate_fn: Evaluation function / 评价函数
        n_trajectories: Number of Morris trajectories / Morris 轨迹数
        n_levels: Number of discretization levels / 离散化水平数
        seed: Random seed / 随机种子

    Returns:
        Dict with mu, mu_star, sigma for each parameter.
    """
    if n_levels < 2:
        raise ValueError(f"n_levels must be at least 2, got {n_levels}")
    if not param_ranges:
        raise ValueError("param_ranges must not be empty")
    if n_trajectories <= 0:
        raise ValueError(f"n_trajectories must be positive, got {n_trajectories}")

    rng = np.random.default_rng(seed)
    param_names = list(param_ranges.keys())
    k = len(param_names)
    delta = 1.0 / (n_levels - 1)

    elementary_effects: dict[str, list[float]] = {name: [] for name in param_names}

    for _ in range(n_trajectories):
        # Random starting point on grid
        x_base = rng.integers(0, n_levels, size=k) / (n_levels - 1)

        # Compute base output
        params_base = {}
        for i, name in enumerate(param_names):
            lo, hi = param_ranges[name]
            params_base[name] = float(lo + x_base[i] * (hi - lo))
        y_base = evaluate_fn(params_base)

        # Perturb each parameter
        for i, name in enumerate(param_names):
            x_pert = x_base.copy()
            direction = 1 if x_base[i] + delta <= 1.0 else -1
            x_pert[i] = x_base[i] + direction * delta

            params_pert = {}
            for j, pname in enumerate(param_names):
                lo, hi = param_ranges[pname]
                params_pert[pname] = float(lo + x_pert[j] * (hi - lo))

            y_pert = evaluate_fn(params_pert)
            ee = (y_pert - y_base) / (direction * delta)
            elementary_effects[name].append(ee)

    results = {}
    for name in param_names:
        ee = np.array(elementary_effects[name])
        results[name] = {
            "mu": float(np.mean(ee)),
            "mu_star": float(np.mean(np.abs(ee))),
            "sigma": float(np.std(ee)),
            "n_effects": len(ee),
        }

    ranking = sorted(results.keys(), key=lambda k: results[k]["mu_star"], reverse=True)

    return {
        "method": "Morris",
        "parameters": results,
        "ranking": ranking,
        "n_trajectories": n_trajectories,
        "n_levels": n_levels,
    }
