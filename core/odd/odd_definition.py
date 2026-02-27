"""ODD (Operational Design Domain) definition and boundary specification.
运行设计域（ODD）定义与边界规格。

Defines the safe operating envelope for the water system using
a six-dimensional parameter space.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DimensionSpec:
    """Specification for one ODD dimension. / ODD 单维度规格。"""

    name: str
    min_value: float
    max_value: float
    unit: str
    warning_margin: float = 0.1  # fraction for extended zone / 扩展域裕度（比例）

    @property
    def range_val(self) -> float:
        """Range of this dimension. / 维度范围。"""
        return self.max_value - self.min_value

    @property
    def warning_lower(self) -> float:
        """Lower warning threshold. / 下限预警阈值。"""
        return self.min_value + self.warning_margin * self.range_val

    @property
    def warning_upper(self) -> float:
        """Upper warning threshold. / 上限预警阈值。"""
        return self.max_value - self.warning_margin * self.range_val


@dataclass
class ODDSpec:
    """Complete ODD specification for a water system.
    水系统完整 ODD 规格。
    """

    dimensions: list[DimensionSpec] = field(default_factory=list)
    _dim_index: dict[str, DimensionSpec] = field(default_factory=dict, repr=False)

    def add_dimension(self, name: str, min_val: float, max_val: float, unit: str, **kwargs) -> None:
        """Add a dimension to the ODD. / 添加 ODD 维度。"""
        dim = DimensionSpec(name=name, min_value=min_val, max_value=max_val, unit=unit, **kwargs)
        self.dimensions.append(dim)
        self._dim_index[name] = dim

    def get_dimension(self, name: str) -> DimensionSpec | None:
        """Get dimension by name (O(1) lookup). / 按名称获取维度。"""
        return self._dim_index.get(name)

    def to_dict(self) -> dict:
        """Serialize to dict. / 序列化为字典。"""
        return {
            "dimensions": [
                {
                    "name": d.name,
                    "min_value": d.min_value,
                    "max_value": d.max_value,
                    "unit": d.unit,
                    "warning_margin": d.warning_margin,
                }
                for d in self.dimensions
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> ODDSpec:
        """Deserialize from dict. / 从字典反序列化。"""
        spec = cls()
        for d in data.get("dimensions", []):
            spec.add_dimension(
                name=d["name"],
                min_val=d["min_value"],
                max_val=d["max_value"],
                unit=d["unit"],
                warning_margin=d.get("warning_margin", 0.1),
            )
        return spec

    @classmethod
    def from_json(cls, path: str | Path) -> ODDSpec:
        """Load from JSON file. / 从 JSON 文件加载。"""
        with open(path) as f:
            return cls.from_dict(json.load(f))


def create_tank_odd(
    h_min: float = 0.1,
    h_max: float = 1.8,
    q_in_max: float = 0.05,
    q_out_max: float = 0.03,
    temp_min: float = 0.0,
    temp_max: float = 40.0,
) -> ODDSpec:
    """Create default ODD for a single-tank system.
    创建单水箱系统的默认 ODD。

    Args:
        h_min: Min water level (m) / 最低水位
        h_max: Max water level (m) / 最高水位
        q_in_max: Max inflow rate (m³/s) / 最大入流量
        q_out_max: Max outflow rate (m³/s) / 最大出流量
        temp_min: Min temperature (°C) / 最低温度
        temp_max: Max temperature (°C) / 最高温度

    Returns:
        ODDSpec for a single-tank system.
    """
    odd = ODDSpec()
    odd.add_dimension("water_level", h_min, h_max, "m")
    odd.add_dimension("inflow_rate", 0.0, q_in_max, "m³/s")
    odd.add_dimension("outflow_rate", 0.0, q_out_max, "m³/s")
    odd.add_dimension("water_quality_turbidity", 0.0, 10.0, "NTU")
    odd.add_dimension("temperature", temp_min, temp_max, "°C")
    odd.add_dimension("structural_pressure", 0.0, 50.0, "kPa")
    return odd
