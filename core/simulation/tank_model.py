"""Tank model — ODE-based single-tank hydraulic model.
水箱模型 — 基于 ODE 的单水箱水力学模型。

Physical equation:
    dh/dt = (Q_in - Q_out) / A
    Q_out = Cd * a * sqrt(2 * g * h)

Where:
    h:    water level (m) / 水位
    A:    tank cross-section area (m²) / 水箱截面积
    Q_in: inflow rate (m³/s) / 入流量
    Q_out: outflow rate (m³/s) / 出流量
    Cd:   discharge coefficient (dimensionless) / 流量系数
    a:    outlet area (m²) / 出口面积
    g:    gravitational acceleration (9.81 m/s²) / 重力加速度
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


GRAVITY: float = 9.81  # m/s²


@dataclass
class TankParams:
    """Parameters for a single-tank model. / 单水箱模型参数。"""

    area: float = 1.0  # Tank cross-section area (m²) / 水箱截面积
    cd: float = 0.6  # Discharge coefficient / 流量系数
    outlet_area: float = 0.01  # Outlet area (m²) / 出口面积
    h_max: float = 2.0  # Maximum water level (m) / 最大水位
    h_min: float = 0.0  # Minimum water level (m) / 最小水位

    def validate(self) -> None:
        """Validate parameter ranges. / 验证参数范围。"""
        if self.area <= 0:
            raise ValueError(f"Tank area must be positive, got {self.area}")
        if self.cd <= 0 or self.cd > 1:
            raise ValueError(f"Discharge coefficient must be in (0, 1], got {self.cd}")
        if self.outlet_area <= 0:
            raise ValueError(f"Outlet area must be positive, got {self.outlet_area}")
        if self.h_max <= self.h_min:
            raise ValueError(f"h_max ({self.h_max}) must be greater than h_min ({self.h_min})")


def compute_outflow(h: float, params: TankParams) -> float:
    """Compute outflow rate using Torricelli's equation.
    基于托里拆利公式计算出流量。

    Args:
        h: Current water level (m) / 当前水位
        params: Tank parameters / 水箱参数

    Returns:
        Outflow rate Q_out (m³/s) / 出流量
    """
    if h <= 0:
        return 0.0
    return params.cd * params.outlet_area * math.sqrt(2.0 * GRAVITY * h)


def tank_ode(h: float, q_in: float, params: TankParams) -> float:
    """Right-hand side of the tank ODE: dh/dt = (Q_in - Q_out) / A.
    水箱 ODE 右端项。

    Args:
        h: Current water level (m) / 当前水位
        q_in: Inflow rate (m³/s) / 入流量
        params: Tank parameters / 水箱参数

    Returns:
        dh/dt (m/s) / 水位变化率
    """
    q_out = compute_outflow(h, params)
    return (q_in - q_out) / params.area
