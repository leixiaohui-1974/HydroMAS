"""HydroOS Compute — L1 Ray-based distributed computation.
HydroOS 计算层 — L1 基于 Ray 的分布式计算。

Modules:
    ray_config       — Ray runtime initialization
    distributed_sim  — Parallel simulation sweeps and Monte Carlo
    distributed_optim — Parallel optimization and sensitivity
    parallel_data    — Parallel data cleaning
    actor_controller — Stateful Ray Actor controllers
"""

from compute.actor_controller import create_mpc_actor
from compute.distributed_optim import parallel_evaluate, parallel_sensitivity
from compute.distributed_sim import (
    monte_carlo_sim,
    parameter_sweep,
    simulate_single,
)
from compute.parallel_data import chunk_timeseries, parallel_clean
from compute.ray_config import init_ray, is_ray_available, shutdown_ray

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
