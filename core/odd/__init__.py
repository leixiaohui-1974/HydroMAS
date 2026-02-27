"""Core ODD module — Operational Design Domain definition and monitoring.
核心 ODD 模块 — 运行设计域定义与监测。
"""

from core.odd.mrc_handler import (
    MRCAction,
    determine_mrc_actions,
    generate_mrc_plan,
)
from core.odd.odd_definition import (
    DimensionSpec,
    ODDSpec,
    create_tank_odd,
)
from core.odd.odd_monitor import (
    Zone,
    check_odd,
    check_odd_series,
    classify_value,
)

__all__ = [
    "DimensionSpec",
    "ODDSpec",
    "create_tank_odd",
    "Zone",
    "classify_value",
    "check_odd",
    "check_odd_series",
    "MRCAction",
    "determine_mrc_actions",
    "generate_mrc_plan",
]
