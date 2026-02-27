"""Ray runtime initialization and configuration.
Ray 运行时初始化与配置。

Supports automatic detection of single-node vs. cluster mode.
MVP uses local single-node mode; cluster mode for future expansion.
"""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)

_initialized = False


def init_ray(num_cpus: int | None = None, **kwargs) -> None:
    """Initialize Ray runtime with automatic mode detection.
    自动检测模式并初始化 Ray 运行时。

    - If RAY_ADDRESS env var is set, connects to existing cluster.
    - Otherwise, starts local single-node mode.
    - No-op if already initialized.

    Args:
        num_cpus: Override CPU count (default: auto-detect) / CPU 数量覆盖
        **kwargs: Additional ray.init() arguments.
    """
    global _initialized

    try:
        import ray
    except ImportError:
        logger.warning("Ray not installed. Distributed features unavailable.")
        return

    if ray.is_initialized():
        _initialized = True
        return

    cluster_address = os.environ.get("RAY_ADDRESS")
    if cluster_address:
        logger.info(f"Connecting to Ray cluster at {cluster_address}")
        ray.init(address=cluster_address, **kwargs)
    else:
        init_kwargs = {"num_cpus": num_cpus} if num_cpus else {}
        init_kwargs.update(kwargs)
        logger.info("Starting Ray in local mode")
        ray.init(**init_kwargs)

    _initialized = True


def shutdown_ray() -> None:
    """Shutdown Ray runtime. / 关闭 Ray 运行时。"""
    global _initialized
    try:
        import ray
        if ray.is_initialized():
            ray.shutdown()
    except ImportError:
        pass
    _initialized = False


_ray_available: bool | None = None


def is_ray_available() -> bool:
    """Check if Ray is installed and can be initialized.
    检查 Ray 是否已安装且可初始化。
    """
    global _ray_available
    if _ray_available is not None:
        return _ray_available
    try:
        import ray  # noqa: F401
        _ray_available = True
    except ImportError:
        _ray_available = False
    return _ray_available
