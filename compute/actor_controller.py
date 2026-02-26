"""Ray Actor-based stateful controllers.
基于 Ray Actor 的有状态控制器。

Persistent controller instances that maintain state across calls,
useful for MPC rolling optimization.
"""

from __future__ import annotations

from compute.ray_config import is_ray_available, init_ray


def create_mpc_actor(
    horizon: int = 10,
    tank_area: float = 1.0,
    dt: float = 1.0,
    **mpc_kwargs,
):
    """Create a Ray Actor-backed MPC controller (or local fallback).
    创建基于 Ray Actor 的 MPC 控制器（或本地回退）。

    Args:
        horizon: MPC prediction horizon / MPC 预测时域
        tank_area: Tank cross-section area / 水箱截面积
        dt: Time step / 时间步长
        **mpc_kwargs: Additional MPC parameters.

    Returns:
        Actor handle (Ray) or local MPCController instance.
    """
    if is_ray_available():
        try:
            import ray
            init_ray()

            @ray.remote
            class MPCControllerActor:
                def __init__(self, h, ta, timestep, **kw):
                    from core.control.mpc_controller import MPCController
                    self.controller = MPCController(
                        horizon=h, tank_area=ta, dt=timestep, **kw
                    )
                    self.state_history = []

                def step(self, current_h, setpoint, q_out_estimate=0.005):
                    action = self.controller.compute(current_h, setpoint, q_out_estimate)
                    self.state_history.append({"h": current_h, "action": action})
                    return action

                def get_history(self):
                    return self.state_history

                def reset(self):
                    self.controller.reset()
                    self.state_history = []

            return MPCControllerActor.remote(horizon, tank_area, dt, **mpc_kwargs)
        except Exception:
            pass

    # Local fallback
    from core.control.mpc_controller import MPCController
    return MPCController(horizon=horizon, tank_area=tank_area, dt=dt, **mpc_kwargs)
