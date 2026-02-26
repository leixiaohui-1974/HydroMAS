"""Core identification module — system parameter estimation.
核心辨识模块 — 系统参数估计。
"""

from core.identification.arx_model import identify_arx, predict_arx
from core.identification.least_squares import identify_tank_params

__all__ = [
    "identify_arx",
    "predict_arx",
    "identify_tank_params",
]
