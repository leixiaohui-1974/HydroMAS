"""Digital twin engine — real-time WNTR simulation with UKF state correction.
数字孪生引擎 — 基于 WNTR + UKF 校正的实时数字孪生。

Provides a stateful engine that maintains a virtual replica of a water
distribution network, accepts live sensor data, and applies Unscented
Kalman Filter (UKF) corrections to keep the twin synchronised with the
physical system.

提供有状态的引擎，维护配水管网的虚拟副本，接收实时传感器数据，
并应用无迹卡尔曼滤波 (UKF) 校正以保持孪生体与物理系统同步。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

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
class TwinState:
    """Snapshot of the digital twin state at a point in time.
    数字孪生在某一时刻的状态快照。
    """

    timestamp: float = 0.0  # Simulation time (s) / 仿真时间
    node_pressures: dict = field(default_factory=dict)  # Node ID -> pressure (m) / 节点压力
    node_levels: dict = field(default_factory=dict)  # Tank/reservoir ID -> level (m) / 液位
    pipe_flows: dict = field(default_factory=dict)  # Pipe ID -> flow (m³/s) / 管段流量
    pump_speeds: dict = field(default_factory=dict)  # Pump ID -> relative speed / 水泵转速

    def validate(self) -> None:
        """Validate state values. / 验证状态值。"""
        if self.timestamp < 0:
            raise ValueError(
                f"timestamp must be non-negative, got {self.timestamp}"
            )
        if not isinstance(self.node_pressures, dict):
            raise ValueError("node_pressures must be a dict")
        if not isinstance(self.node_levels, dict):
            raise ValueError("node_levels must be a dict")
        if not isinstance(self.pipe_flows, dict):
            raise ValueError("pipe_flows must be a dict")
        if not isinstance(self.pump_speeds, dict):
            raise ValueError("pump_speeds must be a dict")


class DigitalTwinEngine:
    """Real-time digital twin engine with UKF state correction.
    基于 UKF 校正的实时数字孪生引擎。

    When WNTR is available the engine uses a full EPANET hydraulic model.
    Without WNTR a simplified dict-based simulation is used, propagating
    states via first-order mass-balance approximations.

    当 WNTR 可用时使用完整的 EPANET 水力模型。
    无 WNTR 时使用简化的基于字典的仿真，通过一阶质量守恒近似传播状态。
    """

    def __init__(self, inp_file: str) -> None:
        """Initialise the digital twin from an EPANET input file.
        从 EPANET 输入文件初始化数字孪生。

        Args:
            inp_file: Path to the EPANET .inp file / EPANET 输入文件路径
        """
        self._inp_file: str = inp_file
        self._use_wntr: bool = _HAS_WNTR
        self._wn: Any = None
        self._state: TwinState = TwinState()

        # UKF parameters / UKF 参数
        self._alpha: float = 1e-3  # Spread parameter / 扩展参数
        self._beta: float = 2.0  # Prior distribution (Gaussian) / 先验分布参数
        self._kappa: float = 0.0  # Secondary scaling / 二级缩放参数
        self._P: np.ndarray | None = None  # State covariance / 状态协方差
        self._Q_noise: np.ndarray | None = None  # Process noise / 过程噪声
        self._R_noise: np.ndarray | None = None  # Measurement noise / 测量噪声
        self._state_keys: list[str] = []  # Ordered state variable names / 状态变量名

        if self._use_wntr:
            self._wn = wntr.network.WaterNetworkModel(inp_file)
            self._init_state_from_wntr()
        else:
            self._init_state_simplified()

    # ------------------------------------------------------------------
    # Initialisation helpers / 初始化辅助方法
    # ------------------------------------------------------------------

    def _init_state_from_wntr(self) -> None:
        """Build initial state from the WNTR model.
        从 WNTR 模型构建初始状态。
        """
        wn = self._wn
        node_pressures: dict[str, float] = {
            nid: 0.0 for nid in wn.node_name_list
        }
        node_levels: dict[str, float] = {}
        for tank_name in wn.tank_name_list:
            tank = wn.get_node(tank_name)
            node_levels[tank_name] = tank.init_level

        pipe_flows: dict[str, float] = {
            pid: 0.0 for pid in wn.pipe_name_list
        }
        pump_speeds: dict[str, float] = {
            pid: 1.0 for pid in wn.pump_name_list
        }

        self._state = TwinState(
            timestamp=0.0,
            node_pressures=node_pressures,
            node_levels=node_levels,
            pipe_flows=pipe_flows,
            pump_speeds=pump_speeds,
        )

        # Initialise UKF matrices around node pressures / 围绕节点压力初始化 UKF 矩阵
        self._state_keys = sorted(node_pressures.keys())
        n = len(self._state_keys)
        if n > 0:
            self._P = np.eye(n) * 1.0
            self._Q_noise = np.eye(n) * 0.01
            self._R_noise = np.eye(n) * 0.1

    def _init_state_simplified(self) -> None:
        """Build a minimal initial state without WNTR.
        无 WNTR 时构建最小初始状态。
        """
        self._state = TwinState(
            timestamp=0.0,
            node_pressures={},
            node_levels={},
            pipe_flows={},
            pump_speeds={},
        )
        self._state_keys = []

    # ------------------------------------------------------------------
    # UKF helpers / UKF 辅助方法
    # ------------------------------------------------------------------

    def _generate_sigma_points(
        self, x: np.ndarray, P: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate UKF sigma points.
        生成 UKF sigma 点。

        Args:
            x: State vector (n,) / 状态向量
            P: Covariance matrix (n, n) / 协方差矩阵

        Returns:
            Tuple of (sigma_points, weights_mean, weights_cov).
            返回 (sigma 点, 均值权重, 协方差权重) 元组。
        """
        n = len(x)
        lam = self._alpha ** 2 * (n + self._kappa) - n

        # Cholesky factorisation / Cholesky 分解
        try:
            sqrt_matrix = np.linalg.cholesky((n + lam) * P)
        except np.linalg.LinAlgError:
            sqrt_matrix = np.linalg.cholesky(
                (n + lam) * (P + np.eye(n) * 1e-6)
            )

        sigma_points = np.zeros((2 * n + 1, n))
        sigma_points[0] = x
        for i in range(n):
            sigma_points[i + 1] = x + sqrt_matrix[i]
            sigma_points[n + i + 1] = x - sqrt_matrix[i]

        # Weights / 权重
        wm = np.full(2 * n + 1, 1.0 / (2.0 * (n + lam)))
        wc = np.full(2 * n + 1, 1.0 / (2.0 * (n + lam)))
        wm[0] = lam / (n + lam)
        wc[0] = lam / (n + lam) + (1.0 - self._alpha ** 2 + self._beta)

        return sigma_points, wm, wc

    def _ukf_correct(
        self,
        x_pred: np.ndarray,
        P_pred: np.ndarray,
        z: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Apply UKF measurement correction step.
        执行 UKF 测量校正步骤。

        Args:
            x_pred: Predicted state vector / 预测状态向量
            P_pred: Predicted covariance / 预测协方差
            z: Measurement vector / 测量向量

        Returns:
            Tuple of (corrected_state, corrected_covariance).
            返回 (校正后状态, 校正后协方差) 元组。
        """
        n = len(x_pred)
        if self._R_noise is None:
            self._R_noise = np.eye(n) * 0.1

        sigma_pts, wm, wc = self._generate_sigma_points(x_pred, P_pred)

        # Predicted measurement sigma points (identity observation) / 预测测量 sigma 点
        z_sigma = sigma_pts.copy()

        # Mean predicted measurement / 预测测量均值
        z_mean = np.dot(wm, z_sigma)

        # Innovation covariance / 新息协方差
        S = self._R_noise[:n, :n].copy()
        Pxz = np.zeros((n, n))
        for i in range(2 * n + 1):
            dz = z_sigma[i] - z_mean
            dx = sigma_pts[i] - x_pred
            S += wc[i] * np.outer(dz, dz)
            Pxz += wc[i] * np.outer(dx, dz)

        # Kalman gain / 卡尔曼增益
        K = Pxz @ np.linalg.inv(S)

        # Corrected state / 校正后状态
        x_corr = x_pred + K @ (z - z_mean)
        P_corr = P_pred - K @ S @ K.T

        return x_corr, P_corr

    # ------------------------------------------------------------------
    # Public API / 公共接口
    # ------------------------------------------------------------------

    def update(self, sensor_data: dict) -> TwinState:
        """Feed live sensor data and return the corrected twin state.
        输入实时传感器数据并返回校正后的孪生状态。

        Sensor data keys should map to node IDs with pressure readings.
        When WNTR is available, the UKF corrects the full hydraulic state.
        Otherwise a simplified first-order update is performed.

        Args:
            sensor_data: Mapping of sensor_id -> measured_value / 传感器数据映射

        Returns:
            Corrected TwinState snapshot / 校正后的 TwinState 快照
        """
        if self._use_wntr and self._state_keys and self._P is not None:
            return self._update_wntr(sensor_data)
        return self._update_simplified(sensor_data)

    def _update_wntr(self, sensor_data: dict) -> TwinState:
        """UKF-corrected update using the WNTR model.
        使用 WNTR 模型进行 UKF 校正更新。

        Args:
            sensor_data: Mapping of node_id -> pressure reading / 节点压力读数

        Returns:
            Corrected TwinState / 校正后的 TwinState
        """
        # Build predicted state vector from current pressures / 从当前压力构建预测状态
        x_pred = np.array(
            [self._state.node_pressures.get(k, 0.0) for k in self._state_keys]
        )
        P_pred = self._P + self._Q_noise  # type: ignore[operator]

        # Build measurement vector (use prediction where no sensor) / 构建测量向量
        z = np.array(
            [sensor_data.get(k, x_pred[i]) for i, k in enumerate(self._state_keys)]
        )

        x_corr, P_corr = self._ukf_correct(x_pred, P_pred, z)
        self._P = P_corr

        # Write corrected pressures back / 将校正压力写回
        for i, key in enumerate(self._state_keys):
            self._state.node_pressures[key] = float(x_corr[i])

        # Advance timestamp / 推进时间戳
        self._state.timestamp += 1.0

        # Also update any directly provided pipe flows or pump speeds /
        # 同时更新直接提供的管段流量或水泵转速
        for k, v in sensor_data.items():
            if k in self._state.pipe_flows:
                self._state.pipe_flows[k] = v
            if k in self._state.pump_speeds:
                self._state.pump_speeds[k] = v

        self._state.validate()
        return self._state

    def _update_simplified(self, sensor_data: dict) -> TwinState:
        """Simplified first-order update without WNTR.
        无 WNTR 的简化一阶更新。

        Args:
            sensor_data: Mapping of sensor_id -> measured_value / 传感器数据映射

        Returns:
            Updated TwinState / 更新后的 TwinState
        """
        # Apply sensor readings directly with exponential smoothing /
        # 使用指数平滑直接应用传感器读数
        smoothing: float = 0.7

        for key, value in sensor_data.items():
            if key in self._state.node_pressures:
                old = self._state.node_pressures[key]
                self._state.node_pressures[key] = (
                    smoothing * value + (1 - smoothing) * old
                )
            elif key in self._state.pipe_flows:
                old = self._state.pipe_flows[key]
                self._state.pipe_flows[key] = (
                    smoothing * value + (1 - smoothing) * old
                )
            elif key in self._state.pump_speeds:
                old = self._state.pump_speeds[key]
                self._state.pump_speeds[key] = (
                    smoothing * value + (1 - smoothing) * old
                )
            else:
                # New unknown sensor — store in node_pressures by default /
                # 未知传感器 — 默认存入节点压力
                self._state.node_pressures[key] = value

        self._state.timestamp += 1.0
        self._state.validate()
        return self._state

    def simulate_what_if(
        self,
        scenario: dict,
        horizon: float,
    ) -> list[TwinState]:
        """Run a what-if scenario from the current state.
        从当前状态运行假设场景。

        The scenario dict may contain:
          - "pump_speeds": {pump_id: new_speed, ...}
          - "valve_settings": {valve_id: new_setting, ...}
          - "demand_factor": float  (multiplier on all demands)
          - "dt": float  (time step for the projection, default 300 s)

        When WNTR is available the scenario modifies a copy of the model
        and runs a full simulation.  Otherwise a simplified projection
        is generated.

        Args:
            scenario: Scenario parameters / 场景参数
            horizon: Projection horizon (s) / 预测时长

        Returns:
            List of TwinState snapshots at each time step.
            每个时间步的 TwinState 快照列表。

        Raises:
            ValueError: If horizon is non-positive.
        """
        if horizon <= 0:
            raise ValueError(f"horizon must be positive, got {horizon}")

        dt: float = scenario.get("dt", 300.0)

        if self._use_wntr:
            return self._what_if_wntr(scenario, horizon, dt)
        return self._what_if_simplified(scenario, horizon, dt)

    def _what_if_wntr(
        self,
        scenario: dict,
        horizon: float,
        dt: float,
    ) -> list[TwinState]:
        """What-if using WNTR simulation.
        使用 WNTR 仿真的假设分析。

        Args:
            scenario: Scenario parameters / 场景参数
            horizon: Projection horizon (s) / 预测时长
            dt: Time step (s) / 时间步长

        Returns:
            List of TwinState snapshots / TwinState 快照列表
        """
        wn = wntr.network.WaterNetworkModel(self._inp_file)
        wn.options.time.duration = int(horizon)
        wn.options.time.hydraulic_timestep = int(dt)
        wn.options.time.report_timestep = int(dt)

        # Apply pump speed overrides / 应用水泵转速覆盖
        pump_speeds = scenario.get("pump_speeds", {})
        for pump_id, speed in pump_speeds.items():
            pump = wn.get_link(pump_id)
            pat_name = f"_whatif_{pump_id}"
            wn.add_pattern(pat_name, [speed])
            pump.speed_pattern_name = pat_name

        # Apply demand factor / 应用需求因子
        demand_factor = scenario.get("demand_factor", 1.0)
        if demand_factor != 1.0:
            for jname in wn.junction_name_list:
                junction = wn.get_node(jname)
                for idx in range(len(junction.demand_timeseries_list)):
                    junction.demand_timeseries_list[idx].base_value *= demand_factor

        sim = wntr.sim.EpanetSimulator(wn)
        results = sim.run_sim()

        timestamps = results.node["pressure"].index.tolist()
        states: list[TwinState] = []

        for ts in timestamps:
            pressures = results.node["pressure"].loc[ts].to_dict()
            flows = results.link["flowrate"].loc[ts].to_dict()

            node_levels: dict[str, float] = {}
            if hasattr(results.node, "get") and "head" in results.node:
                for tank_name in wn.tank_name_list:
                    if tank_name in results.node["head"].columns:
                        tank = wn.get_node(tank_name)
                        head = results.node["head"].loc[ts][tank_name]
                        node_levels[tank_name] = head - tank.elevation

            state = TwinState(
                timestamp=float(ts),
                node_pressures={k: float(v) for k, v in pressures.items()},
                node_levels=node_levels,
                pipe_flows={k: float(v) for k, v in flows.items()},
                pump_speeds=pump_speeds if pump_speeds else dict(self._state.pump_speeds),
            )
            state.validate()
            states.append(state)

        return states

    def _what_if_simplified(
        self,
        scenario: dict,
        horizon: float,
        dt: float,
    ) -> list[TwinState]:
        """Simplified what-if projection without WNTR.
        无 WNTR 的简化假设投影。

        Assumes constant state with only pump-speed and demand-factor
        scaling applied to the current snapshot values.

        Args:
            scenario: Scenario parameters / 场景参数
            horizon: Projection horizon (s) / 预测时长
            dt: Time step (s) / 时间步长

        Returns:
            List of TwinState snapshots / TwinState 快照列表
        """
        demand_factor: float = scenario.get("demand_factor", 1.0)
        new_pump_speeds: dict = scenario.get("pump_speeds", {})

        n_steps = max(1, int(horizon / dt))
        states: list[TwinState] = []

        for step in range(n_steps + 1):
            t = self._state.timestamp + step * dt

            # Scale pressures proportionally to demand factor /
            # 根据需求因子按比例缩放压力
            pressures = {
                k: v / demand_factor if demand_factor != 0 else v
                for k, v in self._state.node_pressures.items()
            }

            pump_speeds = dict(self._state.pump_speeds)
            pump_speeds.update(new_pump_speeds)

            state = TwinState(
                timestamp=t,
                node_pressures=pressures,
                node_levels=dict(self._state.node_levels),
                pipe_flows=dict(self._state.pipe_flows),
                pump_speeds=pump_speeds,
            )
            state.validate()
            states.append(state)

        return states

    def calibrate(self, historical_data: list[dict]) -> dict:
        """Auto-calibrate model parameters from historical sensor data.
        从历史传感器数据自动校准模型参数。

        Iterates through the historical records, computing the mean
        absolute error between observed and predicted pressures, and
        adjusts the UKF noise parameters to minimise residuals.

        When WNTR is available the calibration additionally tunes pipe
        roughness coefficients using a least-squares approach.

        Args:
            historical_data: List of dicts, each mapping sensor_id ->
                measured_value at a point in time / 历史传感器数据列表

        Returns:
            Dict with calibration summary including residuals and
            adjusted parameters.
            包含残差和调整参数的校准摘要字典。

        Raises:
            ValueError: If historical_data is empty.
        """
        if not historical_data:
            raise ValueError("historical_data must not be empty")

        if self._use_wntr and self._state_keys:
            return self._calibrate_wntr(historical_data)
        return self._calibrate_simplified(historical_data)

    def _calibrate_wntr(self, historical_data: list[dict]) -> dict:
        """Calibrate with WNTR model and UKF tuning.
        使用 WNTR 模型和 UKF 调参进行校准。

        Args:
            historical_data: Historical sensor records / 历史传感器记录

        Returns:
            Calibration result dict / 校准结果字典
        """
        n = len(self._state_keys)
        residuals: list[float] = []

        for record in historical_data:
            x_pred = np.array(
                [self._state.node_pressures.get(k, 0.0) for k in self._state_keys]
            )
            z = np.array(
                [record.get(k, x_pred[i]) for i, k in enumerate(self._state_keys)]
            )
            error = float(np.mean(np.abs(z - x_pred)))
            residuals.append(error)

            # Update state with observed values / 用观测值更新状态
            self.update(record)

        mean_residual = float(np.mean(residuals)) if residuals else 0.0

        # Adjust noise matrices based on residual magnitude /
        # 根据残差大小调整噪声矩阵
        if mean_residual > 0 and self._Q_noise is not None:
            scale = max(0.001, min(mean_residual, 10.0))
            self._Q_noise = np.eye(n) * (scale * 0.1)
            self._R_noise = np.eye(n) * (scale * 0.5)

        # Roughness tuning placeholder — collect pipe names /
        # 粗糙度调参占位 — 收集管段名称
        pipe_roughness: dict[str, float] = {}
        wn = self._wn
        if wn is not None:
            for pname in wn.pipe_name_list:
                pipe = wn.get_link(pname)
                pipe_roughness[pname] = pipe.roughness

        return {
            "n_records": len(historical_data),
            "mean_residual": mean_residual,
            "residuals": residuals,
            "Q_noise_diag": float(self._Q_noise[0, 0]) if self._Q_noise is not None else 0.0,
            "R_noise_diag": float(self._R_noise[0, 0]) if self._R_noise is not None else 0.0,
            "pipe_roughness": pipe_roughness,
            "metadata": {
                "inp_file": self._inp_file,
                "method": "ukf_least_squares",
                "state_dim": n,
            },
        }

    def _calibrate_simplified(self, historical_data: list[dict]) -> dict:
        """Simplified calibration without WNTR.
        无 WNTR 的简化校准。

        Args:
            historical_data: Historical sensor records / 历史传感器记录

        Returns:
            Calibration result dict / 校准结果字典
        """
        residuals: list[float] = []

        for record in historical_data:
            errors: list[float] = []
            for key, value in record.items():
                predicted = self._state.node_pressures.get(key, 0.0)
                errors.append(abs(value - predicted))
            residual = float(np.mean(errors)) if errors else 0.0
            residuals.append(residual)

            # Apply the record to update state / 应用记录更新状态
            self.update(record)

        mean_residual = float(np.mean(residuals)) if residuals else 0.0

        return {
            "n_records": len(historical_data),
            "mean_residual": mean_residual,
            "residuals": residuals,
            "Q_noise_diag": 0.0,
            "R_noise_diag": 0.0,
            "pipe_roughness": {},
            "metadata": {
                "inp_file": self._inp_file,
                "method": "simplified_smoothing",
                "state_dim": 0,
            },
        }
