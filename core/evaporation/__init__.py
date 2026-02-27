"""Evaporation loss calculation module — cooling tower, calcination, red mud models.
蒸发损耗计算模块 — 冷却塔、焙烧、赤泥模型。
"""

from core.evaporation.merkel_model import CoolingTowerParams, calc_evaporation_merkel, calc_evap_rate
from core.evaporation.calcination_model import CalcinationParams, calc_calcination_evap
from core.evaporation.red_mud_model import RedMudParams, calc_red_mud_water

__all__ = [
    "CoolingTowerParams", "calc_evaporation_merkel", "calc_evap_rate",
    "CalcinationParams", "calc_calcination_evap",
    "RedMudParams", "calc_red_mud_water",
]
