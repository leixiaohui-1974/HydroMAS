"""PID controller for water level regulation.
PID 控制器 — 水位调节。

Implements a discrete PID controller with anti-windup and output clamping.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class PIDParams:
    """PID controller parameters. / PID 控制器参数。"""

    kp: float = 1.0  # Proportional gain / 比例增益
    ki: float = 0.1  # Integral gain / 积分增益
    kd: float = 0.05  # Derivative gain / 微分增益
    output_min: float = 0.0  # Minimum output (m³/s) / 最小输出
    output_max: float = 0.05  # Maximum output (m³/s) / 最大输出
    anti_windup: bool = True  # Enable anti-windup / 启用抗积分饱和


class PIDController:
    """Discrete PID controller with anti-windup.
    带抗积分饱和的离散 PID 控制器。

    Usage:
        pid = PIDController(PIDParams(kp=2.0, ki=0.1, kd=0.01))
        for each timestep:
            u = pid.compute(setpoint=1.0, measured=current_level, dt=1.0)
    """

    def __init__(self, params: PIDParams | None = None):
        self.params = params or PIDParams()
        self._integral: float = 0.0
        self._prev_error: float | None = None
        self._history: deque[dict] = deque(maxlen=10000)

    def reset(self) -> None:
        """Reset controller state. / 重置控制器状态。"""
        self._integral = 0.0
        self._prev_error = None
        self._history.clear()

    def compute(self, setpoint: float, measured: float, dt: float = 1.0) -> float:
        """Compute PID control output.
        计算 PID 控制输出。

        Args:
            setpoint: Desired water level (m) / 目标水位
            measured: Current water level (m) / 当前水位
            dt: Time step (s) / 时间步长

        Returns:
            Control output (inflow rate, m³/s) / 控制输出（入流量）
        """
        if dt <= 0:
            raise ValueError(f"dt must be positive, got {dt}")

        import math
        if not (math.isfinite(setpoint) and math.isfinite(measured)):
            raise ValueError(
                f"setpoint and measured must be finite, got "
                f"setpoint={setpoint}, measured={measured}"
            )

        error = setpoint - measured

        # Proportional term
        p_term = self.params.kp * error

        # Integral term with anti-windup
        self._integral += error * dt
        i_term = self.params.ki * self._integral

        # Derivative term
        if self._prev_error is not None:
            d_term = self.params.kd * (error - self._prev_error) / dt
        else:
            d_term = 0.0

        self._prev_error = error

        # Raw output
        output = p_term + i_term + d_term

        # Clamp output
        clamped = max(self.params.output_min, min(self.params.output_max, output))

        # Anti-windup: back-calculate integral if output is saturated
        if self.params.anti_windup and not math.isclose(clamped, output):
            self._integral -= error * dt  # undo the integral accumulation

        self._history.append({
            "error": error,
            "p_term": p_term,
            "i_term": i_term,
            "d_term": d_term,
            "output_raw": output,
            "output": clamped,
        })

        return clamped

    def get_history(self) -> list[dict]:
        """Return control history. / 返回控制历史记录。"""
        return list(self._history)


def run_pid_control(
    setpoint: float,
    initial_h: float,
    duration: float,
    dt: float = 1.0,
    pid_params: dict | None = None,
    tank_params: dict | None = None,
) -> dict:
    """Run closed-loop PID control simulation on a tank.
    在水箱上运行闭环 PID 控制仿真。

    Args:
        setpoint: Target water level (m) / 目标水位
        initial_h: Initial water level (m) / 初始水位
        duration: Simulation duration (s) / 仿真时长
        dt: Time step (s) / 时间步长
        pid_params: PID parameters dict / PID 参数
        tank_params: Tank parameters dict / 水箱参数

    Returns:
        Dict with time series of level, control output, error, etc.
    """
    import numpy as np

    from core.simulation.tank_model import TankParams, compute_outflow, tank_ode

    params = PIDParams(**(pid_params or {}))
    tank = TankParams(**(tank_params or {}))
    tank.validate()

    pid = PIDController(params)
    n_steps = round(duration / dt)

    time_arr = np.zeros(n_steps + 1)
    h_arr = np.zeros(n_steps + 1)
    u_arr = np.zeros(n_steps)
    error_arr = np.zeros(n_steps)
    qout_arr = np.zeros(n_steps + 1)

    h = initial_h

    for i in range(n_steps + 1):
        time_arr[i] = i * dt
        h_arr[i] = h
        qout_arr[i] = compute_outflow(h, tank)

        if i < n_steps:
            u = pid.compute(setpoint, h, dt)
            u_arr[i] = u
            error_arr[i] = setpoint - h

            # Simulate one step (Euler)
            dhdt = tank_ode(h, u, tank)
            h = h + dhdt * dt
            h = max(tank.h_min, min(tank.h_max, h))

    return {
        "time": time_arr.tolist(),
        "water_level": h_arr.tolist(),
        "control_output": u_arr.tolist(),
        "error": error_arr.tolist(),
        "outflow": qout_arr.tolist(),
        "setpoint": setpoint,
        "pid_params": {"kp": params.kp, "ki": params.ki, "kd": params.kd},
        "metadata": {"solver": "Euler", "steps": n_steps, "dt": dt},
    }
