"""Model Predictive Controller (MPC) for water level regulation.
模型预测控制器 — 基于线性化模型的滚动优化。

Uses a linearized tank model for prediction and scipy.optimize for the
quadratic programming problem at each step.
"""

from __future__ import annotations

from collections import deque

import numpy as np
from scipy.optimize import minimize


class MPCController:
    """MPC controller using linearized tank model.
    使用线性化水箱模型的 MPC 控制器。

    The controller solves an optimization problem at each time step:
        min  Σ (h_k - h_ref)² * Q + Σ (u_k)² * R
        s.t. h_{k+1} = A_d * h_k + B_d * u_k
             u_min <= u_k <= u_max
             h_min <= h_k <= h_max
    """

    def __init__(
        self,
        horizon: int = 10,
        q_weight: float = 10.0,
        r_weight: float = 1.0,
        u_min: float = 0.0,
        u_max: float = 0.05,
        h_min: float = 0.0,
        h_max: float = 2.0,
        tank_area: float = 1.0,
        dt: float = 1.0,
    ):
        """Initialize MPC controller.

        Args:
            horizon: Prediction horizon (steps) / 预测时域
            q_weight: State tracking weight / 状态跟踪权重
            r_weight: Control effort weight / 控制量权重
            u_min: Minimum control input (m³/s) / 最小控制输入
            u_max: Maximum control input (m³/s) / 最大控制输入
            h_min: Minimum water level (m) / 最低水位
            h_max: Maximum water level (m) / 最高水位
            tank_area: Tank cross-section area (m²) / 水箱截面积
            dt: Time step (s) / 时间步长
        """
        if tank_area <= 0:
            raise ValueError(f"tank_area must be positive, got {tank_area}")
        if dt <= 0:
            raise ValueError(f"dt must be positive, got {dt}")

        self.horizon = horizon
        self.q_weight = q_weight
        self.r_weight = r_weight
        self.u_min = u_min
        self.u_max = u_max
        self.h_min = h_min
        self.h_max = h_max
        self.tank_area = tank_area
        self.dt = dt
        self._bounds = [(self.u_min, self.u_max)] * self.horizon
        self._prev_solution: np.ndarray | None = None
        self._history: deque[dict] = deque(maxlen=10000)

    def _predict(self, h0: float, u_seq: np.ndarray, q_out_est: float,
                 h_buf: np.ndarray | None = None) -> np.ndarray:
        """Predict future water levels given control sequence.
        给定控制序列预测未来水位。

        Uses simplified linear model: h_{k+1} = h_k + (u_k - q_out_est) * dt / A
        """
        if h_buf is None:
            h_buf = np.zeros(self.horizon + 1)
        h_buf[0] = h0
        dt_over_a = self.dt / self.tank_area
        for k in range(self.horizon):
            dh = (u_seq[k] - q_out_est) * dt_over_a
            h_buf[k + 1] = max(self.h_min, min(self.h_max, h_buf[k] + dh))
        return h_buf

    def compute(
        self,
        current_h: float,
        setpoint: float,
        q_out_estimate: float = 0.005,
    ) -> float:
        """Compute MPC control action for the current step.
        计算当前步的 MPC 控制动作。

        Args:
            current_h: Current water level (m) / 当前水位
            setpoint: Target water level (m) / 目标水位
            q_out_estimate: Estimated outflow (m³/s) / 估计出流量

        Returns:
            Optimal control input for the current step (m³/s).
        """
        # Warm-start from shifted previous solution
        if self._prev_solution is not None:
            u0 = np.roll(self._prev_solution, -1)
            u0[-1] = u0[-2] if len(u0) > 1 else (self.u_min + self.u_max) / 2
        else:
            u0 = np.full(self.horizon, (self.u_min + self.u_max) / 2)

        h_buf = np.zeros(self.horizon + 1)  # pre-allocate once, reuse per eval

        def cost(u_seq: np.ndarray) -> float:
            self._predict(current_h, u_seq, q_out_estimate, h_buf)
            state_cost = self.q_weight * np.sum((h_buf[1:] - setpoint) ** 2)
            control_cost = self.r_weight * np.sum(u_seq**2)
            return state_cost + control_cost

        result = minimize(cost, u0, method="L-BFGS-B", bounds=self._bounds)
        optimal_u = float(result.x[0]) if result.success else (self.u_min + self.u_max) / 2

        if result.success:
            self._prev_solution = result.x

        self._history.append({
            "current_h": current_h,
            "setpoint": setpoint,
            "optimal_u": float(optimal_u),
            "cost": float(result.fun),
            "converged": bool(result.success),
        })

        return float(optimal_u)

    def get_history(self) -> list[dict]:
        """Return control history. / 返回控制历史。"""
        return list(self._history)

    def reset(self) -> None:
        """Reset controller state. / 重置控制器状态。"""
        self._history.clear()
        self._prev_solution = None


def run_mpc_control(
    setpoint: float,
    initial_h: float,
    duration: float,
    dt: float = 1.0,
    mpc_params: dict | None = None,
    tank_params: dict | None = None,
) -> dict:
    """Run closed-loop MPC control simulation on a tank.
    在水箱上运行闭环 MPC 控制仿真。

    Args:
        setpoint: Target water level (m) / 目标水位
        initial_h: Initial water level (m) / 初始水位
        duration: Simulation duration (s) / 仿真时长
        dt: Time step (s) / 时间步长
        mpc_params: MPC parameters dict / MPC 参数
        tank_params: Tank parameters dict / 水箱参数

    Returns:
        Dict with time series of level, control output, etc.
    """
    from core.simulation.tank_model import TankParams, tank_ode, compute_outflow

    tank = TankParams(**(tank_params or {}))
    tank.validate()

    mpc_kw = dict(mpc_params) if mpc_params else {}
    mpc_kw.setdefault("tank_area", tank.area)
    mpc_kw.setdefault("dt", dt)
    mpc = MPCController(**mpc_kw)

    n_steps = round(duration / dt)
    time_arr = np.zeros(n_steps + 1)
    h_arr = np.zeros(n_steps + 1)
    u_arr = np.zeros(n_steps)
    qout_arr = np.zeros(n_steps + 1)

    h = initial_h

    for i in range(n_steps + 1):
        time_arr[i] = i * dt
        h_arr[i] = h
        q_out = compute_outflow(h, tank)
        qout_arr[i] = q_out

        if i < n_steps:
            u = mpc.compute(h, setpoint, q_out_estimate=q_out)
            u_arr[i] = u

            # Simulate one step (Euler)
            dhdt = tank_ode(h, u, tank)
            h = h + dhdt * dt
            h = max(tank.h_min, min(tank.h_max, h))

    return {
        "time": time_arr.tolist(),
        "water_level": h_arr.tolist(),
        "control_output": u_arr.tolist(),
        "outflow": qout_arr.tolist(),
        "setpoint": setpoint,
        "mpc_params": {
            "horizon": mpc.horizon,
            "q_weight": mpc.q_weight,
            "r_weight": mpc.r_weight,
        },
        "metadata": {"solver": "Euler+MPC", "steps": n_steps, "dt": dt},
    }
