"""Configuration loader for HydroOS data files.
配置加载器 — 从 data/ 目录加载 JSON 配置。

Loads tank_config.json and odd_specs.json, providing typed access
to default parameters used across the platform.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(filename: str) -> dict:
    """Load a JSON file from the data/ directory.
    从 data/ 目录加载 JSON 文件。
    """
    path = _DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with open(path) as f:
        return json.load(f)


def load_tank_config() -> dict[str, Any]:
    """Load default tank configuration from data/tank_config.json.
    从 data/tank_config.json 加载默认水箱配置。

    Returns:
        Dict with keys: tank_params, simulation_defaults, control_defaults,
        supply_capacity, target_level, description.
    """
    return _load_json("tank_config.json")


def load_odd_specs() -> dict[str, Any]:
    """Load ODD specification from data/odd_specs.json.
    从 data/odd_specs.json 加载 ODD 规格。

    Returns:
        Dict with keys: dimensions (list of dim specs), description.
    """
    return _load_json("odd_specs.json")


def get_default_tank_params() -> dict:
    """Get default tank parameters from config.
    获取默认水箱参数。

    Returns:
        Dict with area, cd, outlet_area, h_max, h_min.
    """
    config = load_tank_config()
    return config["tank_params"]


def get_default_pid_params() -> dict:
    """Get default PID controller parameters from config.
    获取默认 PID 控制器参数。

    Returns:
        Dict with kp, ki, kd, output_min, output_max.
    """
    config = load_tank_config()
    return config["control_defaults"]["pid"]


def get_default_mpc_params() -> dict:
    """Get default MPC controller parameters from config.
    获取默认 MPC 控制器参数。

    Returns:
        Dict with horizon, q_weight, r_weight, u_min, u_max.
    """
    config = load_tank_config()
    return config["control_defaults"]["mpc"]


def get_default_simulation_params() -> dict:
    """Get default simulation parameters from config.
    获取默认仿真参数。

    Returns:
        Dict with duration, dt, initial_h, solver.
    """
    config = load_tank_config()
    return config["simulation_defaults"]
