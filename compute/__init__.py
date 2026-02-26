"""HydroOS Compute — L1 Ray-based distributed computation.
HydroOS 计算层 — L1 基于 Ray 的分布式计算。

Modules:
    ray_config       — Ray runtime initialization
    distributed_sim  — Parallel simulation sweeps and Monte Carlo
    distributed_optim — Parallel optimization and sensitivity
    parallel_data    — Parallel data cleaning
    actor_controller — Stateful Ray Actor controllers
"""

from compute.ray_config import init_ray, shutdown_ray, is_ray_available
from compute.distributed_sim import (
    simulate_single,
    parameter_sweep,
    monte_carlo_sim,
)
from compute.distributed_optim import parallel_sensitivity, parallel_evaluate
from compute.parallel_data import parallel_clean, chunk_timeseries
from compute.actor_controller import create_mpc_actor

__all__ = [
    "init_ray",
    "shutdown_ray",
    "is_ray_available",
    "simulate_single",
    "parameter_sweep",
    "monte_carlo_sim",
    "parallel_sensitivity",
    "parallel_evaluate",
    "parallel_clean",
    "chunk_timeseries",
    "create_mpc_actor",
]
