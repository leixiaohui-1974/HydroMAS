"""Calcination evaporation model — moisture removal in rotary kiln / flash calciner.
焙烧蒸发模型 — 回转窑/闪速焙烧中的水分去除。

Physical basis:
    E_cal = slurry_flow × moisture_content × η(T)

Where:
    slurry_flow:      volumetric flow of wet slurry (m³/h) / 湿浆料体积流量
    moisture_content:  mass fraction of water in slurry (0-1) / 浆料含水率
    η(T):             temperature-dependent evaporation efficiency / 温度相关蒸发效率
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# Physical constants
CP_WATER: float = 4.186      # kJ/(kg·℃), specific heat capacity of water
LV_BASE: float = 2450.0      # kJ/kg, latent heat of vaporization at ~20℃
WATER_DENSITY: float = 1000.0  # kg/m³


@dataclass
class CalcinationParams:
    """Parameters for calcination evaporation model. / 焙烧蒸发模型参数。"""

    slurry_flow_m3h: float = 50.0       # Wet slurry flow (m³/h) / 湿浆料流量
    moisture_content: float = 0.45       # Water mass fraction (0-1) / 含水率
    calcination_temp: float = 1050.0     # Calcination temperature (℃) / 焙烧温度

    def validate(self) -> None:
        """Validate parameter ranges. / 验证参数范围。"""
        if self.slurry_flow_m3h <= 0:
            raise ValueError(
                f"Slurry flow must be positive, got {self.slurry_flow_m3h}"
            )
        if self.moisture_content <= 0 or self.moisture_content >= 1:
            raise ValueError(
                f"Moisture content must be in (0, 1), got {self.moisture_content}"
            )
        if self.calcination_temp <= 0:
            raise ValueError(
                f"Calcination temperature must be positive, got {self.calcination_temp}"
            )


def _calc_efficiency(temp: float) -> float:
    """Compute temperature-dependent evaporation efficiency η(T).
    计算温度相关的蒸发效率 η(T)。

    At higher calcination temperatures, evaporation is more complete.
    Uses a saturating exponential model approaching 1.0.

    Args:
        temp: Calcination temperature (℃) / 焙烧温度

    Returns:
        Efficiency factor (0-1) / 效率系数
    """
    # Asymptotic efficiency: η = 1 - exp(-T / T_ref)
    # At T=500℃ → ~0.92, at T=1050℃ → ~0.99
    t_ref = 200.0
    eta = 1.0 - math.exp(-temp / t_ref)
    return max(0.0, min(1.0, eta))


def calc_calcination_evap(params: CalcinationParams) -> dict:
    """Calculate evaporation loss from calcination process.
    计算焙烧过程的蒸发损耗。

    Args:
        params: Calcination parameters / 焙烧参数

    Returns:
        Dict with evaporation rate, daily total, and energy consumption.
        包含蒸发速率、日总量和能耗的字典。
    """
    params.validate()

    # Temperature-dependent evaporation efficiency
    eta = _calc_efficiency(params.calcination_temp)

    # Water volume evaporated per hour (m³/h)
    # slurry_flow × moisture_content gives the water volume fraction
    evap_rate_m3h = params.slurry_flow_m3h * params.moisture_content * eta

    # Daily evaporation (m³/d)
    evap_daily_m3 = evap_rate_m3h * 24.0

    # Energy consumption estimate (kWh)
    # Energy = mass_water × [Cp × (100 - 20) + L_v + Cp_steam × (T_calc - 100)]
    # Simplified: sensible heating to 100℃ + latent heat + superheating
    mass_water_kgh = evap_rate_m3h * WATER_DENSITY  # kg/h
    sensible_heat = CP_WATER * 80.0                  # kJ/kg, heating from ~20℃ to 100℃
    superheat = 2.0 * (params.calcination_temp - 100.0)  # kJ/kg, rough Cp_steam
    energy_per_kg = sensible_heat + LV_BASE + superheat  # kJ/kg
    energy_kwh = mass_water_kgh * energy_per_kg / 3600.0  # kWh (per hour)

    return {
        "evap_rate_m3h": evap_rate_m3h,
        "evap_daily_m3": evap_daily_m3,
        "energy_consumption_kwh": energy_kwh,
        "details": {
            "efficiency": eta,
            "mass_water_kgh": mass_water_kgh,
            "energy_per_kg_kj": energy_per_kg,
            "calcination_temp": params.calcination_temp,
        },
    }
