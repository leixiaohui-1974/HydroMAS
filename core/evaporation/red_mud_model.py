"""Red mud water carry-out model — moisture entrained in stacked red mud.
赤泥带水模型 — 堆存赤泥中夹带的水分。

Physical basis:
    Q_rm = M_rm × w_rm / (1 - w_rm)

Where:
    M_rm:  dry red mud mass (t/d) / 干赤泥质量
    w_rm:  moisture ratio (mass water / mass wet mud, 0-1) / 含水率
    Q_rm:  water carried out (m³/d) / 带出水量
"""

from __future__ import annotations

from dataclasses import dataclass

# Conversion constant
WATER_DENSITY_T_M3: float = 1.0  # Water density ~1 t/m³ for unit conversion


@dataclass
class RedMudParams:
    """Parameters for red mud water carry-out model. / 赤泥带水模型参数。"""

    mud_dry_mass_td: float = 500.0   # Dry red mud mass (t/d) / 干赤泥质量
    moisture_ratio: float = 0.55      # Moisture ratio (0-1) / 含水率

    def validate(self) -> None:
        """Validate parameter ranges. / 验证参数范围。"""
        if self.mud_dry_mass_td <= 0:
            raise ValueError(
                f"Dry mud mass must be positive, got {self.mud_dry_mass_td}"
            )
        if self.moisture_ratio <= 0 or self.moisture_ratio >= 1:
            raise ValueError(
                f"Moisture ratio must be in (0, 1), got {self.moisture_ratio}"
            )


def calc_red_mud_water(params: RedMudParams) -> dict:
    """Calculate water carried out by stacked red mud.
    计算赤泥堆存带出的水量。

    The water carried out is computed from the dry mass and moisture ratio:
        Q_rm = M_rm × w_rm / (1 - w_rm)
    where w_rm is the ratio of water mass to total (wet) mud mass.

    Args:
        params: Red mud parameters / 赤泥参数

    Returns:
        Dict with daily and hourly water carry-out volumes.
        包含日和小时带水量的字典。
    """
    params.validate()

    # Water carried out per day (t/d → m³/d via density ~1 t/m³)
    # Q_rm = M_dry × w / (1 - w)
    water_carry_td = (
        params.mud_dry_mass_td
        * params.moisture_ratio
        / (1.0 - params.moisture_ratio)
    )
    water_carry_m3d = water_carry_td / WATER_DENSITY_T_M3

    # Hourly rate
    water_carry_m3h = water_carry_m3d / 24.0

    return {
        "water_carry_m3d": water_carry_m3d,
        "water_carry_m3h": water_carry_m3h,
        "details": {
            "mud_dry_mass_td": params.mud_dry_mass_td,
            "moisture_ratio": params.moisture_ratio,
            "water_carry_td": water_carry_td,
        },
    }
