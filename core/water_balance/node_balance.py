"""Node-level water balance — single node accounting and residual.
节点水平衡 — 单节点水量核算与残差计算。

Physical equation:
    R = Q_in - Q_out - Q_loss - Q_evap - dV/dt

Where:
    R:      residual (m³/s) — ideally zero / 残差（理想为零）
    Q_in:   total inflow (m³/s) / 总入流量
    Q_out:  total outflow (m³/s) / 总出流量
    Q_loss: losses such as leaks (m³/s) / 漏损量
    Q_evap: evaporation loss (m³/s) / 蒸发损失
    dV/dt:  rate of volume change (m³/s) / 蓄水量变化率
"""

from __future__ import annotations

from dataclasses import dataclass

_VALID_NODE_TYPES = ("intake", "pool", "workshop", "reuse", "wastewater")


@dataclass
class BalanceNode:
    """A single node in the water balance network. / 水平衡网络中的单个节点。"""

    node_id: str
    node_type: str  # intake / pool / workshop / reuse / wastewater
    q_in: float = 0.0  # Inflow rate (m³/s) / 入流量
    q_out: float = 0.0  # Outflow rate (m³/s) / 出流量
    q_loss: float = 0.0  # Loss rate (m³/s) / 漏损量
    q_evap: float = 0.0  # Evaporation rate (m³/s) / 蒸发损失
    volume: float = 0.0  # Current volume (m³) / 当前蓄水量
    capacity: float = 0.0  # Maximum capacity (m³) / 最大容量

    def validate(self) -> None:
        """Validate node parameters. / 验证节点参数。"""
        if self.node_type not in _VALID_NODE_TYPES:
            raise ValueError(
                f"node_type must be one of {_VALID_NODE_TYPES}, "
                f"got '{self.node_type}'"
            )
        if self.q_in < 0:
            raise ValueError(f"q_in must be non-negative, got {self.q_in}")
        if self.q_out < 0:
            raise ValueError(f"q_out must be non-negative, got {self.q_out}")
        if self.q_loss < 0:
            raise ValueError(f"q_loss must be non-negative, got {self.q_loss}")
        if self.q_evap < 0:
            raise ValueError(f"q_evap must be non-negative, got {self.q_evap}")
        if self.volume < 0:
            raise ValueError(f"volume must be non-negative, got {self.volume}")
        if self.capacity < 0:
            raise ValueError(f"capacity must be non-negative, got {self.capacity}")
        if self.capacity < self.volume:
            raise ValueError(
                f"capacity ({self.capacity}) must be >= volume ({self.volume})"
            )


def calc_node_residual(node: BalanceNode, dv_dt: float = 0.0) -> float:
    """Calculate the water balance residual for a single node.
    计算单节点水平衡残差。

    R = Q_in - Q_out - Q_loss - Q_evap - dV/dt
    A residual near zero indicates a balanced node.

    Args:
        node: Balance node with flow data / 含流量数据的平衡节点
        dv_dt: Rate of volume change (m³/s) / 蓄水量变化率

    Returns:
        Residual value R (m³/s). / 残差值
    """
    return node.q_in - node.q_out - node.q_loss - node.q_evap - dv_dt


def calc_reuse_rate(total_reuse: float, total_intake: float) -> float:
    """Calculate water reuse rate (recycling ratio).
    计算水重复利用率（循环比）。

    Args:
        total_reuse: Total reused water volume (m³/s) / 总回用水量
        total_intake: Total fresh water intake (m³/s) / 总新水取水量

    Returns:
        Reuse rate as a ratio [0, 1]. Returns 0.0 if total_intake is zero.
        重复利用率，取值 [0, 1]。当总取水量为零时返回 0.0。
    """
    if total_intake <= 0:
        return 0.0
    return min(total_reuse / total_intake, 1.0)
