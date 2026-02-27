"""Ray Actor-based stateful controllers.
基于 Ray Actor 的有状态控制器。

Persistent controller instances that maintain state across calls,
useful for MPC rolling optimization.
"""

from __future__ import annotations

import logging
from typing import Any

from compute.ray_config import init_ray, is_ray_available

logger = logging.getLogger(__name__)


class MPCActorAdapter:
    """Provide local-like API on top of a Ray actor handle.

    Unknown attributes are proxied to the underlying actor handle so callers
    can still access native ``.remote`` APIs when needed.
    """

    def __init__(self, actor_handle: Any):
        self._actor = actor_handle


    @property
    def actor_handle(self) -> Any:
        """Expose raw Ray actor handle for advanced usage."""
        return self._actor

    def __getattr__(self, item: str) -> Any:
        """Proxy unknown attributes to the underlying actor handle."""
        return getattr(self._actor, item)

    def compute(self, current_h: float, setpoint: float, q_out_estimate: float = 0.005) -> float:
        """Run one MPC step and return control action."""
        import ray

        return ray.get(
            self._actor.step.remote(
                current_h=current_h,
                setpoint=setpoint,
                q_out_estimate=q_out_estimate,
            )
        )

    def get_history(self):
        """Return internal actor history."""
        import ray

        return ray.get(self._actor.get_history.remote())

    def reset(self):
        """Reset actor state."""
        import ray

        ray.get(self._actor.reset.remote())


def create_mpc_actor(
    horizon: int = 10,
    tank_area: float = 1.0,
    dt: float = 1.0,
    **mpc_kwargs,
) -> Any:
    """Create a Ray Actor-backed MPC controller (or local fallback).
    创建基于 Ray Actor 的 MPC 控制器（或本地回退）。

    Args:
        horizon: MPC prediction horizon / MPC 预测时域
        tank_area: Tank cross-section area / 水箱截面积
        dt: Time step / 时间步长
        **mpc_kwargs: Additional MPC parameters.

    Returns:
        MPCActorAdapter (Ray-backed) or local MPCController instance.
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

            actor_handle = MPCControllerActor.remote(horizon, tank_area, dt, **mpc_kwargs)
            return MPCActorAdapter(actor_handle)
        except Exception as e:
            logger.warning(f"Ray MPC actor creation failed, falling back to local: {e}")

    # Local fallback
    from core.control.mpc_controller import MPCController
    return MPCController(horizon=horizon, tank_area=tank_area, dt=dt, **mpc_kwargs)
