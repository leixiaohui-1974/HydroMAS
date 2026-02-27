"""Alumina process water demand — dissolution, decomposition, evaporation workshops.
氧化铝工艺用水需求 — 溶出、分解、蒸发各工段用水计算。

Empirical-mechanism hybrid model for Bayer-process alumina refining.
基于拜耳法氧化铝精炼的经验-机理混合模型。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProcessState:
    """Snapshot of alumina production operating state. / 氧化铝生产运行状态快照。"""

    ore_feed_td: float = 0.0        # Ore feed rate (t/d) / 矿石给料速率
    alkali_concentration: float = 0.0  # Alkali concentration (g/L) / 碱浓度
    dissolution_temp: float = 0.0   # Dissolution temperature (℃) / 溶出温度
    decomposition_temp: float = 0.0  # Decomposition temperature (℃) / 分解温度
    evaporation_ratio: float = 0.0  # Evaporation ratio (dimensionless) / 蒸发比

    def validate(self) -> None:
        """Validate parameter ranges. / 验证参数范围。"""
        if self.ore_feed_td < 0:
            raise ValueError(
                f"Ore feed rate must be >= 0, got {self.ore_feed_td}"
            )
        if self.alkali_concentration < 0:
            raise ValueError(
                f"Alkali concentration must be >= 0, got {self.alkali_concentration}"
            )
        if self.dissolution_temp < 0:
            raise ValueError(
                f"Dissolution temperature must be >= 0, got {self.dissolution_temp}"
            )
        if self.decomposition_temp < 0:
            raise ValueError(
                f"Decomposition temperature must be >= 0, got {self.decomposition_temp}"
            )
        if self.evaporation_ratio < 0:
            raise ValueError(
                f"Evaporation ratio must be >= 0, got {self.evaporation_ratio}"
            )


def calc_dissolution_water(
    ore_feed: float,
    alkali_conc: float,
    temp: float,
) -> float:
    """Calculate dissolution workshop water demand.
    计算溶出工段用水需求。

    Empirical-mechanism hybrid formula:
        Q = ore_feed * (2.5 + 0.003 * temp) / (1 + alkali_conc / 300)

    Args:
        ore_feed: Ore feed rate (t/d) / 矿石给料速率
        alkali_conc: Alkali concentration (g/L) / 碱浓度
        temp: Dissolution temperature (℃) / 溶出温度

    Returns:
        Water demand (m³/d) / 用水需求
    """
    if ore_feed < 0:
        raise ValueError(f"ore_feed must be >= 0, got {ore_feed}")
    if alkali_conc < 0:
        raise ValueError(f"alkali_conc must be >= 0, got {alkali_conc}")
    if temp < 0:
        raise ValueError(f"temp must be >= 0, got {temp}")

    return ore_feed * (2.5 + 0.003 * temp) / (1.0 + alkali_conc / 300.0)


def calc_decomposition_water(
    seed_ratio: float,
    temp: float,
    tank_volume: float,
) -> float:
    """Calculate decomposition workshop water demand.
    计算分解工段用水需求。

    Formula:
        Q = tank_volume * 0.02 * (1 + seed_ratio * 0.1) * (1 + (temp - 50) * 0.005)

    Args:
        seed_ratio: Seed-to-liquid ratio (dimensionless) / 种子比
        temp: Decomposition temperature (℃) / 分解温度
        tank_volume: Decomposition tank volume (m³) / 分解槽容积

    Returns:
        Water demand (m³/d) / 用水需求
    """
    if tank_volume < 0:
        raise ValueError(f"tank_volume must be >= 0, got {tank_volume}")

    return tank_volume * 0.02 * (1.0 + seed_ratio * 0.1) * (1.0 + (temp - 50.0) * 0.005)


def calc_evaporation_makeup(
    evap_ratio: float,
    circulation_volume: float,
) -> float:
    """Calculate evaporation makeup water demand.
    计算蒸发补水需求。

    85% of evaporated volume needs to be replenished:
        Q = circulation_volume * evap_ratio * 0.85

    Args:
        evap_ratio: Evaporation ratio (dimensionless) / 蒸发比
        circulation_volume: Circulation volume (m³/d) / 循环量

    Returns:
        Makeup water demand (m³/d) / 补水需求
    """
    if evap_ratio < 0:
        raise ValueError(f"evap_ratio must be >= 0, got {evap_ratio}")
    if circulation_volume < 0:
        raise ValueError(f"circulation_volume must be >= 0, got {circulation_volume}")

    return circulation_volume * evap_ratio * 0.85


def calc_total_process_demand(state: ProcessState) -> dict:
    """Calculate total water demand across all alumina workshops.
    计算所有氧化铝工段的总用水需求。

    Workshops: dissolution, decomposition, evaporation, red mud washing,
    and calcination cooling.
    工段：溶出、分解、蒸发、赤泥洗涤、焙烧冷却。

    Args:
        state: Current process operating state / 当前工艺运行状态

    Returns:
        Dict with per-workshop demands and total (m³/d).
        包含各工段用水及总量的字典。
    """
    state.validate()

    # Dissolution workshop / 溶出工段
    ws_dissolution = calc_dissolution_water(
        ore_feed=state.ore_feed_td,
        alkali_conc=state.alkali_concentration,
        temp=state.dissolution_temp,
    )

    # Decomposition workshop — default tank volume 500 m³, seed ratio 3.0
    # 分解工段 — 默认槽容积 500 m³、种子比 3.0
    default_tank_volume = 500.0
    default_seed_ratio = 3.0
    ws_decomposition = calc_decomposition_water(
        seed_ratio=default_seed_ratio,
        temp=state.decomposition_temp,
        tank_volume=default_tank_volume,
    )

    # Evaporation workshop — default circulation volume 2000 m³/d
    # 蒸发工段 — 默认循环量 2000 m³/d
    default_circulation_volume = 2000.0
    ws_evaporation = calc_evaporation_makeup(
        evap_ratio=state.evaporation_ratio,
        circulation_volume=default_circulation_volume,
    )

    # Red mud washing — proportional to ore feed (1.5 m³ per tonne)
    # 赤泥洗涤 — 与矿石给料成正比（每吨 1.5 m³）
    ws_red_mud = state.ore_feed_td * 1.5

    # Calcination cooling — proportional to ore feed (0.8 m³ per tonne)
    # 焙烧冷却 — 与矿石给料成正比（每吨 0.8 m³）
    ws_calcination = state.ore_feed_td * 0.8

    total = ws_dissolution + ws_decomposition + ws_evaporation + ws_red_mud + ws_calcination

    return {
        "ws_dissolution": ws_dissolution,
        "ws_decomposition": ws_decomposition,
        "ws_evaporation": ws_evaporation,
        "ws_red_mud": ws_red_mud,
        "ws_calcination": ws_calcination,
        "total": total,
    }
