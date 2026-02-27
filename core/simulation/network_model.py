"""Network model — EPANET/WNTR-based water distribution network model.
管网模型 — 基于 EPANET/WNTR 的配水管网模型。

Provides functions for loading EPANET input files, running hydraulic
simulations, and evaluating leak / pump scenarios using the WNTR library.

提供加载 EPANET 输入文件、运行水力仿真、以及评估泄漏/水泵场景的功能。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    import wntr  # type: ignore
    _HAS_WNTR = True
except ImportError:  # pragma: no cover
    _HAS_WNTR = False


def _require_wntr() -> None:
    """Raise if WNTR is not installed. / 若未安装 WNTR 则抛出异常。"""
    if not _HAS_WNTR:
        raise ValueError(
            "WNTR is required but not installed. "
            "Install it with: pip install wntr"
        )


@dataclass
class NetworkParams:
    """Parameters describing a water distribution network. / 配水管网参数。"""

    inp_file: str = ""  # Path to EPANET .inp file / EPANET 输入文件路径
    n_nodes: int = 0  # Number of nodes / 节点数
    n_pipes: int = 0  # Number of pipes / 管段数
    n_pumps: int = 0  # Number of pumps / 水泵数
    n_valves: int = 0  # Number of valves / 阀门数
    total_length_m: float = 0.0  # Total pipe length (m) / 管道总长度

    def validate(self) -> None:
        """Validate parameter ranges. / 验证参数范围。"""
        if self.n_nodes < 0:
            raise ValueError(f"n_nodes must be non-negative, got {self.n_nodes}")
        if self.n_pipes < 0:
            raise ValueError(f"n_pipes must be non-negative, got {self.n_pipes}")
        if self.n_pumps < 0:
            raise ValueError(f"n_pumps must be non-negative, got {self.n_pumps}")
        if self.n_valves < 0:
            raise ValueError(f"n_valves must be non-negative, got {self.n_valves}")
        if self.total_length_m < 0:
            raise ValueError(
                f"total_length_m must be non-negative, got {self.total_length_m}"
            )

    @classmethod
    def from_inp(cls, inp_file: str) -> NetworkParams:
        """Create NetworkParams by parsing an EPANET input file via WNTR.
        通过 WNTR 解析 EPANET 输入文件创建管网参数。

        Args:
            inp_file: Path to the .inp file / EPANET 输入文件路径

        Returns:
            Populated NetworkParams instance / 填充完成的管网参数实例
        """
        _require_wntr()
        wn = wntr.network.WaterNetworkModel(inp_file)

        total_length = sum(
            pipe.length for pipe in wn.pipe_name_list
            for pipe in [wn.get_link(pipe)]
        )

        params = cls(
            inp_file=inp_file,
            n_nodes=len(wn.node_name_list),
            n_pipes=len(wn.pipe_name_list),
            n_pumps=len(wn.pump_name_list),
            n_valves=len(wn.valve_name_list),
            total_length_m=total_length,
        )
        params.validate()
        return params


def load_network(inp_file: str) -> tuple:
    """Load an EPANET network via WNTR.
    通过 WNTR 加载 EPANET 管网。

    Args:
        inp_file: Path to the EPANET .inp file / EPANET 输入文件路径

    Returns:
        Tuple of (NetworkParams, wntr.network.WaterNetworkModel).
        返回 (管网参数, WNTR 管网模型) 元组。
    """
    _require_wntr()
    wn = wntr.network.WaterNetworkModel(inp_file)
    params = NetworkParams.from_inp(inp_file)
    return params, wn


def run_hydraulic_sim(
    inp_file: str,
    duration: float,
    dt: float = 300.0,
) -> dict:
    """Run a hydraulic simulation on an EPANET network.
    对 EPANET 管网运行水力仿真。

    Args:
        inp_file: Path to the EPANET .inp file / EPANET 输入文件路径
        duration: Simulation duration (s) / 仿真时长
        dt: Hydraulic time step (s), default 300 / 水力时间步长，默认 300

    Returns:
        Dict with node_pressures, node_demands, pipe_flows,
        pipe_velocities, and timestamps arrays.
        包含节点压力、节点需水量、管段流量、管段流速及时间戳的字典。

    Raises:
        ValueError: If WNTR is not installed, or dt/duration are invalid.
    """
    _require_wntr()

    if dt <= 0:
        raise ValueError(f"dt must be positive, got {dt}")
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")

    wn = wntr.network.WaterNetworkModel(inp_file)
    wn.options.time.duration = int(duration)
    wn.options.time.hydraulic_timestep = int(dt)
    wn.options.time.report_timestep = int(dt)

    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()

    timestamps = results.node["pressure"].index.tolist()
    node_pressures = results.node["pressure"].to_dict(orient="list")
    node_demands = results.node["demand"].to_dict(orient="list")
    pipe_flows = results.link["flowrate"].to_dict(orient="list")
    pipe_velocities = results.link["velocity"].to_dict(orient="list")

    return {
        "node_pressures": node_pressures,
        "node_demands": node_demands,
        "pipe_flows": pipe_flows,
        "pipe_velocities": pipe_velocities,
        "timestamps": timestamps,
        "metadata": {
            "inp_file": inp_file,
            "duration": duration,
            "dt": dt,
        },
    }


def run_leak_scenario(
    inp_file: str,
    leak_node: str,
    leak_area: float,
    duration: float,
) -> dict:
    """Simulate a leak scenario at a specified node.
    在指定节点模拟泄漏场景。

    A leak emitter is added to *leak_node* with the given discharge area,
    and a full hydraulic simulation is run for *duration* seconds.

    Args:
        inp_file: Path to the EPANET .inp file / EPANET 输入文件路径
        leak_node: Node ID where the leak occurs / 泄漏节点 ID
        leak_area: Leak orifice area (m²) / 泄漏孔口面积
        duration: Simulation duration (s) / 仿真时长

    Returns:
        Dict with node_pressures, node_demands, pipe_flows,
        leak_demand (leak node demand series), and timestamps.
        包含节点压力、节点需水量、管段流量、泄漏需水量及时间戳的字典。

    Raises:
        ValueError: If WNTR is not installed, or parameters are invalid.
    """
    _require_wntr()

    if leak_area <= 0:
        raise ValueError(f"leak_area must be positive, got {leak_area}")
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")

    wn = wntr.network.WaterNetworkModel(inp_file)
    wn.options.time.duration = int(duration)

    node = wn.get_node(leak_node)
    node.add_leak(wn, area=leak_area, start_time=0, end_time=int(duration))

    sim = wntr.sim.WNTRSimulator(wn)
    results = sim.run_sim()

    timestamps = results.node["pressure"].index.tolist()
    node_pressures = results.node["pressure"].to_dict(orient="list")
    node_demands = results.node["demand"].to_dict(orient="list")
    pipe_flows = results.link["flowrate"].to_dict(orient="list")

    leak_demand = (
        results.node["demand"][leak_node].tolist()
        if leak_node in results.node["demand"].columns
        else []
    )

    return {
        "node_pressures": node_pressures,
        "node_demands": node_demands,
        "pipe_flows": pipe_flows,
        "leak_demand": leak_demand,
        "timestamps": timestamps,
        "metadata": {
            "inp_file": inp_file,
            "leak_node": leak_node,
            "leak_area": leak_area,
            "duration": duration,
        },
    }


def run_pump_scenario(
    inp_file: str,
    pump_id: str,
    speed_profile: list,
    duration: float,
) -> dict:
    """Simulate a pump speed-change scenario.
    模拟水泵变速场景。

    Applies a piecewise speed profile to the specified pump and runs a
    full hydraulic simulation for *duration* seconds.

    Args:
        inp_file: Path to the EPANET .inp file / EPANET 输入文件路径
        pump_id: Pump link ID / 水泵链接 ID
        speed_profile: List of (time_s, relative_speed) pairs / 转速时序
        duration: Simulation duration (s) / 仿真时长

    Returns:
        Dict with node_pressures, pipe_flows, pump_flows,
        pump_energy, and timestamps.
        包含节点压力、管段流量、水泵流量、水泵能耗及时间戳的字典。

    Raises:
        ValueError: If WNTR is not installed, or parameters are invalid.
    """
    _require_wntr()

    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")
    if not speed_profile:
        raise ValueError("speed_profile must not be empty")

    wn = wntr.network.WaterNetworkModel(inp_file)
    wn.options.time.duration = int(duration)

    pump = wn.get_link(pump_id)
    pat_name = f"_speed_{pump_id}"
    speed_values = [sp[1] for sp in speed_profile]
    wn.add_pattern(pat_name, speed_values)
    pump.speed_pattern_name = pat_name

    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()

    timestamps = results.node["pressure"].index.tolist()
    node_pressures = results.node["pressure"].to_dict(orient="list")
    pipe_flows = results.link["flowrate"].to_dict(orient="list")

    pump_flows = (
        results.link["flowrate"][pump_id].tolist()
        if pump_id in results.link["flowrate"].columns
        else []
    )

    return {
        "node_pressures": node_pressures,
        "pipe_flows": pipe_flows,
        "pump_flows": pump_flows,
        "timestamps": timestamps,
        "metadata": {
            "inp_file": inp_file,
            "pump_id": pump_id,
            "speed_profile": speed_profile,
            "duration": duration,
        },
    }
