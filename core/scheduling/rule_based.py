"""Rule-based scheduler for simple water management.
规则调度器 — 基于 if-else 逻辑的简单水管理。

Implements threshold-based scheduling rules commonly used in practice.
"""

from __future__ import annotations


def schedule_rule_based(
    current_level: float,
    target_level: float = 1.0,
    min_level: float = 0.2,
    max_level: float = 1.8,
    supply_capacity: float = 0.05,
    current_demand: float = 0.01,
) -> dict:
    """Determine inflow rate using threshold-based rules.
    使用阈值规则确定入流量。

    Rules:
        1. If level < min_level: open full supply (emergency fill)
        2. If level < target - 0.2: increase inflow to 80% capacity
        3. If level ≈ target (±0.1): match inflow to demand
        4. If level > target + 0.2: reduce inflow to 20% capacity
        5. If level > max_level: shut off inflow (emergency)

    Args:
        current_level: Current water level (m) / 当前水位
        target_level: Target water level (m) / 目标水位
        min_level: Minimum safe level (m) / 最低安全水位
        max_level: Maximum safe level (m) / 最高安全水位
        supply_capacity: Maximum inflow rate (m³/s) / 最大供水能力
        current_demand: Current outflow demand (m³/s) / 当前需水量

    Returns:
        Dict with recommended inflow and rule applied.
    """
    if current_level >= max_level:
        return {
            "inflow_rate": 0.0,
            "rule": "emergency_shutoff",
            "priority": "critical",
            "message": f"Level {current_level:.2f}m >= max {max_level:.2f}m: shutting off inflow",
        }

    if current_level <= min_level:
        return {
            "inflow_rate": supply_capacity,
            "rule": "emergency_fill",
            "priority": "critical",
            "message": f"Level {current_level:.2f}m <= min {min_level:.2f}m: full supply",
        }

    if current_level < target_level - 0.2:
        rate = supply_capacity * 0.8
        return {
            "inflow_rate": rate,
            "rule": "increase_supply",
            "priority": "high",
            "message": f"Level {current_level:.2f}m below target: increasing supply to {rate:.4f}",
        }

    if current_level > target_level + 0.2:
        rate = supply_capacity * 0.2
        return {
            "inflow_rate": rate,
            "rule": "reduce_supply",
            "priority": "normal",
            "message": f"Level {current_level:.2f}m above target: reducing supply to {rate:.4f}",
        }

    # Near target — match demand
    return {
        "inflow_rate": current_demand,
        "rule": "match_demand",
        "priority": "normal",
        "message": f"Level {current_level:.2f}m near target: matching demand {current_demand:.4f}",
    }
