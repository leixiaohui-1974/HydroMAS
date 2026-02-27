"""Merkel model — cooling tower evaporation loss estimation.
Merkel 模型 — 冷却塔蒸发损耗估算。

Physical basis:
    E ≈ Q × Cp × (T_in - T_out) / L_v × K_evap

Where:
    Q:      circulation water flow (m³/h) / 循环水流量
    Cp:     specific heat capacity of water, 4.186 kJ/(kg·℃) / 水的比热容
    T_in:   inlet water temperature (℃) / 进水温度
    T_out:  outlet water temperature (℃) / 出水温度
    L_v:    latent heat of vaporization, ~2450 kJ/kg / 汽化潜热
    K_evap: empirical correction factor f(t_wb, wind_speed) / 经验修正系数
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Physical constants
CP_WATER: float = 4.186       # kJ/(kg·℃), specific heat capacity of water
WATER_DENSITY: float = 1000.0  # kg/m³
LV_BASE: float = 2450.0       # kJ/kg, latent heat of vaporization at ~20℃


@dataclass
class CoolingTowerParams:
    """Parameters for a cooling tower evaporation model. / 冷却塔蒸发模型参数。"""

    water_flow_m3h: float = 500.0     # Circulation water flow (m³/h) / 循环水流量
    t_in: float = 42.0                # Inlet water temperature (℃) / 进水温度
    t_out: float = 32.0               # Outlet water temperature (℃) / 出水温度
    n_cells: int = 4                  # Number of cells / 冷却塔单元数
    fan_power_kw: float = 55.0        # Fan power per cell (kW) / 风机功率

    def validate(self) -> None:
        """Validate parameter ranges. / 验证参数范围。"""
        if self.water_flow_m3h <= 0:
            raise ValueError(
                f"Water flow must be positive, got {self.water_flow_m3h}"
            )
        if self.t_in <= self.t_out:
            raise ValueError(
                f"Inlet temperature ({self.t_in}) must be greater than "
                f"outlet temperature ({self.t_out})"
            )
        if self.n_cells <= 0:
            raise ValueError(
                f"Number of cells must be positive, got {self.n_cells}"
            )
        if self.fan_power_kw < 0:
            raise ValueError(
                f"Fan power must be non-negative, got {self.fan_power_kw}"
            )


def _calc_k_evap(t_wb: float, wind_speed: float) -> float:
    """Compute empirical evaporation correction factor K_evap.
    计算经验蒸发修正系数 K_evap。

    K_evap ranges approximately 0.85–1.15 depending on weather conditions.
    Higher wet-bulb temperature and higher wind speed increase evaporation.

    Args:
        t_wb: Wet-bulb temperature (℃) / 湿球温度
        wind_speed: Wind speed (m/s) / 风速

    Returns:
        Empirical correction factor (dimensionless) / 经验修正系数
    """
    # Base correction from wet-bulb temperature (higher t_wb → more evap)
    k_wb = 1.0 + 0.003 * (t_wb - 20.0)
    # Wind speed correction (moderate wind enhances evap, diminishing returns)
    k_wind = 1.0 + 0.02 * math.sqrt(max(0.0, wind_speed))
    k = k_wb * k_wind
    # Clamp to physical range
    return max(0.85, min(1.15, k))


def calc_evaporation_merkel(
    params: CoolingTowerParams,
    weather: dict,
) -> dict:
    """Calculate cooling tower evaporation using Merkel-based energy balance.
    基于 Merkel 能量平衡计算冷却塔蒸发量。

    Args:
        params: Cooling tower parameters / 冷却塔参数
        weather: Weather conditions dict with keys / 气象条件字典:
            - t_db: Dry-bulb temperature (℃) / 干球温度
            - t_wb: Wet-bulb temperature (℃) / 湿球温度
            - humidity: Relative humidity (0-1) / 相对湿度
            - wind_speed: Wind speed (m/s) / 风速

    Returns:
        Dict with evaporation results and detailed breakdown.
        包含蒸发结果和详细分解的字典。
    """
    params.validate()

    t_db = float(weather.get("t_db", 35.0))
    t_wb = float(weather.get("t_wb", 28.0))
    humidity = float(weather.get("humidity", 0.6))
    wind_speed = float(weather.get("wind_speed", 2.0))

    delta_t = params.t_in - params.t_out

    # Heat rejected by cooling water (kJ/h)
    # Q_heat = flow (m³/h) × density (kg/m³) × Cp (kJ/(kg·℃)) × ΔT (℃)
    q_heat_kjh = params.water_flow_m3h * WATER_DENSITY * CP_WATER * delta_t

    # Latent heat of vaporization adjusted for average temperature
    t_avg = (params.t_in + params.t_out) / 2.0
    latent_heat = LV_BASE - 2.36 * (t_avg - 20.0)  # kJ/kg, temperature correction

    # Empirical correction factor
    k_evap = _calc_k_evap(t_wb, wind_speed)

    # Evaporation mass rate (kg/h)
    evap_mass_kgh = q_heat_kjh / latent_heat * k_evap

    # Convert to volumetric rate (m³/h)
    evap_rate_m3h = evap_mass_kgh / WATER_DENSITY

    # Daily evaporation (m³/d)
    evap_daily_m3 = evap_rate_m3h * 24.0

    # Evaporation ratio (fraction of circulation flow lost to evaporation)
    evap_ratio = evap_rate_m3h / params.water_flow_m3h

    return {
        "evap_rate_m3h": evap_rate_m3h,
        "evap_daily_m3": evap_daily_m3,
        "evap_ratio": evap_ratio,
        "details": {
            "latent_heat": latent_heat,
            "k_evap": k_evap,
            "q_heat_kjh": q_heat_kjh,
            "evap_mass_kgh": evap_mass_kgh,
            "delta_t": delta_t,
            "t_avg": t_avg,
            "weather": {
                "t_db": t_db,
                "t_wb": t_wb,
                "humidity": humidity,
                "wind_speed": wind_speed,
            },
            "n_cells": params.n_cells,
            "fan_power_kw": params.fan_power_kw,
        },
    }


def calc_evap_rate(
    t_in: float,
    t_out: float,
    water_flow: float,
    t_wb: float,
) -> float:
    """Simplified evaporation rate calculation returning just m³/h.
    简化蒸发速率计算，仅返回 m³/h。

    Args:
        t_in: Inlet water temperature (℃) / 进水温度
        t_out: Outlet water temperature (℃) / 出水温度
        water_flow: Circulation water flow (m³/h) / 循环水流量
        t_wb: Wet-bulb temperature (℃) / 湿球温度

    Returns:
        Evaporation rate (m³/h) / 蒸发速率
    """
    if t_in <= t_out:
        raise ValueError(
            f"Inlet temperature ({t_in}) must be greater than "
            f"outlet temperature ({t_out})"
        )
    if water_flow <= 0:
        raise ValueError(f"Water flow must be positive, got {water_flow}")

    delta_t = t_in - t_out
    t_avg = (t_in + t_out) / 2.0
    latent_heat = LV_BASE - 2.36 * (t_avg - 20.0)
    k_evap = _calc_k_evap(t_wb, wind_speed=2.0)

    q_heat_kjh = water_flow * WATER_DENSITY * CP_WATER * delta_t
    evap_mass_kgh = q_heat_kjh / latent_heat * k_evap
    return evap_mass_kgh / WATER_DENSITY
