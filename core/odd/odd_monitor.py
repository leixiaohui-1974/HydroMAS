"""ODD real-time monitoring and zone classification.
ODD 实时监测与区域判定。

Three-zone classification:
    - Normal: All parameters within ODD → autonomous operation
    - Extended: Parameters approaching boundaries → warning + human confirmation
    - MRC: Parameters outside ODD → trigger Minimal Risk Condition
"""

from __future__ import annotations

from typing import Literal

from core.odd.odd_definition import ODDSpec, DimensionSpec


Zone = Literal["normal", "extended", "mrc"]


def classify_value(value: float, dim: DimensionSpec) -> Zone:
    """Classify a single value against an ODD dimension.
    对单个值进行 ODD 维度分类。

    Args:
        value: Current value / 当前值
        dim: ODD dimension specification / ODD 维度规格

    Returns:
        Zone classification.
    """
    import math
    if not math.isfinite(value):
        return "mrc"
    if value < dim.min_value or value > dim.max_value:
        return "mrc"
    if value < dim.warning_lower or value > dim.warning_upper:
        return "extended"
    return "normal"


def check_odd(
    current_state: dict[str, float],
    odd_spec: ODDSpec | None = None,
) -> dict:
    """Check current system state against ODD boundaries.
    检查当前系统状态是否在 ODD 边界内。

    Args:
        current_state: Dict of {dimension_name: current_value} / 当前状态
        odd_spec: ODD specification (uses default tank ODD if None) / ODD 规格

    Returns:
        Dict with overall zone, per-dimension results, and violations.
    """
    if odd_spec is None:
        from core.odd.odd_definition import create_tank_odd
        odd_spec = create_tank_odd()

    results = []
    violations = []
    overall_zone: Zone = "normal"

    for dim in odd_spec.dimensions:
        if dim.name not in current_state:
            continue

        value = current_state[dim.name]
        zone = classify_value(value, dim)

        result = {
            "dimension": dim.name,
            "value": value,
            "zone": zone,
            "min": dim.min_value,
            "max": dim.max_value,
            "unit": dim.unit,
        }
        results.append(result)

        if zone == "mrc":
            overall_zone = "mrc"
            violations.append({
                "dimension": dim.name,
                "value": value,
                "bound_violated": "lower" if value < dim.min_value else "upper",
                "limit": dim.min_value if value < dim.min_value else dim.max_value,
                "unit": dim.unit,
            })
        elif zone == "extended" and overall_zone != "mrc":
            overall_zone = "extended"

    return {
        "zone": overall_zone,
        "violations": violations,
        "dimension_results": results,
        "n_checked": len(results),
        "n_violations": len(violations),
    }


def check_odd_series(
    state_series: list[dict[str, float]],
    time_series: list[float] | None = None,
    odd_spec: ODDSpec | None = None,
) -> dict:
    """Check a time series of states against ODD (for forecast/predictive monitoring).
    检查状态时序是否在 ODD 内（用于预报/预测监测）。

    Args:
        state_series: List of state dicts over time / 时序状态列表
        time_series: Optional time values / 可选时间值
        odd_spec: ODD specification / ODD 规格

    Returns:
        Dict with time-to-breach, worst zone, and per-step results.
    """
    if not state_series:
        return {
            "worst_zone": "normal",
            "time_to_breach": None,
            "n_steps": 0,
            "step_results": [],
        }

    if time_series is not None and len(time_series) != len(state_series):
        raise ValueError(
            f"time_series length ({len(time_series)}) must match "
            f"state_series length ({len(state_series)})"
        )

    # Pre-resolve odd_spec once to avoid reconstructing per step
    if odd_spec is None:
        from core.odd.odd_definition import create_tank_odd
        odd_spec = create_tank_odd()

    worst_zone: Zone = "normal"
    time_to_breach: float | None = None
    step_results = []

    for i, state in enumerate(state_series):
        result = check_odd(state, odd_spec)
        step_results.append(result)

        if result["zone"] == "mrc" and worst_zone != "mrc":
            worst_zone = "mrc"
            if time_to_breach is None and time_series is not None:
                time_to_breach = time_series[i]
            elif time_to_breach is None:
                time_to_breach = float(i)
        elif result["zone"] == "extended" and worst_zone == "normal":
            worst_zone = "extended"

    n_violations = sum(
        1 for r in step_results if r.get("zone") == "mrc"
    )
    return {
        "worst_zone": worst_zone,
        "time_to_breach": time_to_breach,
        "n_steps": len(state_series),
        "n_violations": n_violations,
        "step_results": step_results,
    }
