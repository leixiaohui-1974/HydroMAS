"""Process-water coupling module — alumina production water demand calculation.
工艺-水耦合模块 — 氧化铝生产用水需求计算。
"""

from core.process_coupling.alumina_process import (
    ProcessState,
    calc_decomposition_water,
    calc_dissolution_water,
    calc_evaporation_makeup,
    calc_total_process_demand,
)

__all__ = [
    "ProcessState",
    "calc_dissolution_water",
    "calc_decomposition_water",
    "calc_evaporation_makeup",
    "calc_total_process_demand",
]
