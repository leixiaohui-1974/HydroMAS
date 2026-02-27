"""Shared test fixtures for HydroOS-Agent test suite.
HydroOS-Agent 测试套件共享 fixture。
"""

import asyncio
import importlib.util
from inspect import signature
from pathlib import Path

import pytest
import numpy as np

from core.simulation.tank_model import TankParams
from core.simulation.simulator import run_simulation
from core.odd.odd_definition import create_tank_odd


def _has_module(module_name: str) -> bool:
    """Return True when a module can be imported in current environment."""
    return importlib.util.find_spec(module_name) is not None


def pytest_ignore_collect(collection_path, config):
    """Skip optional web API tests when FastAPI is not installed."""
    path = Path(str(collection_path))
    if "tests/test_web" in path.as_posix() and not _has_module("fastapi"):
        return True
    return False


def pytest_configure(config):
    """Register markers used by the suite when pytest-asyncio is unavailable."""
    config.addinivalue_line("markers", "asyncio: mark async test coroutine")

def pytest_collection_modifyitems(config, items):
    """Skip FastAPI-dependent tests when web deps are unavailable."""
    if _has_module("fastapi"):
        return

    fastapi_targets = (
        "tests/test_web/",
        "tests/test_core/test_r3_fixes.py::TestGZipMiddleware",
        "tests/test_core/test_r3_fixes.py::TestHSTSHeader",
        "tests/test_core/test_r3_fixes.py::TestValueErrorTruncation",
        "tests/test_core/test_r3_fixes.py::TestObjectiveLiteral",
        "tests/test_core/test_r4_fixes.py::TestCORSDefault",
        "tests/test_core/test_r5_fixes.py::TestReportEndpointsBounded",
        "tests/test_core/test_r5_fixes.py::TestOpenAPIProduction",
        "tests/test_core/test_r5_fixes.py::TestCSPHeaders",
        "tests/test_core/test_r6_fixes.py::TestRolePathValidation",
    )
    marker = pytest.mark.skip(reason="fastapi is not installed in this environment")
    for item in items:
        if any(target in item.nodeid for target in fastapi_targets):
            item.add_marker(marker)


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Run async tests without requiring pytest-asyncio plugin."""
    if _has_module("pytest_asyncio"):
        return None

    test_func = pyfuncitem.obj
    if not asyncio.iscoroutinefunction(test_func):
        return None

    kwargs = {
        name: pyfuncitem.funcargs[name]
        for name in signature(test_func).parameters
        if name in pyfuncitem.funcargs
    }
    asyncio.run(test_func(**kwargs))
    return True


@pytest.fixture
def tank_params():
    """Default tank parameters for testing."""
    return TankParams(area=1.0, cd=0.6, outlet_area=0.01, h_max=2.0, h_min=0.0)


@pytest.fixture
def tank_params_dict():
    """Default tank parameters as dict."""
    return {"area": 1.0, "cd": 0.6, "outlet_area": 0.01, "h_max": 2.0, "h_min": 0.0}


@pytest.fixture
def sample_simulation():
    """Run a standard simulation and return results."""
    return run_simulation(
        duration=300,
        dt=1.0,
        q_in_profile=[(0, 0.01), (100, 0.03), (200, 0.01)],
        initial_h=0.5,
    )


@pytest.fixture
def sample_water_level_series():
    """Generate a sample water level time series with noise."""
    rng = np.random.default_rng(42)
    n = 200
    t = np.arange(n, dtype=float)
    # Simulate a tank with step inflow
    h = np.zeros(n)
    h[0] = 0.5
    for i in range(1, n):
        q_in = 0.01 if i < 100 else 0.03
        q_out = 0.6 * 0.01 * np.sqrt(2 * 9.81 * max(h[i - 1], 0))
        h[i] = h[i - 1] + (q_in - q_out) / 1.0
        h[i] = max(0, min(2.0, h[i]))
    return h.tolist()


@pytest.fixture
def sample_noisy_series():
    """Water level series with noise, outliers, and NaN values."""
    rng = np.random.default_rng(42)
    base = np.linspace(0.5, 1.2, 100)
    noisy = base + rng.normal(0, 0.02, 100)
    noisy[25] = 5.0    # outlier
    noisy[60] = -1.0   # outlier
    noisy[80] = float("nan")  # missing
    return noisy.tolist()


@pytest.fixture
def odd_spec():
    """Default ODD spec for tank."""
    return create_tank_odd()


@pytest.fixture
def normal_state():
    """A state within ODD normal zone."""
    return {"water_level": 1.0, "inflow_rate": 0.02, "outflow_rate": 0.01}


@pytest.fixture
def mrc_state():
    """A state outside ODD (MRC zone)."""
    return {"water_level": 2.5}


@pytest.fixture
def extended_state():
    """A state in ODD extended zone."""
    return {"water_level": 0.15}


@pytest.fixture
def sample_demand_forecast():
    """Sample demand forecast for scheduling tests."""
    return [0.01, 0.012, 0.015, 0.02, 0.018, 0.015, 0.012, 0.01, 0.01, 0.01]


@pytest.fixture
def pid_params():
    """Default PID parameters."""
    return {"kp": 2.0, "ki": 0.1, "kd": 0.05, "output_min": 0.0, "output_max": 0.05}


@pytest.fixture
def mpc_params():
    """Default MPC parameters."""
    return {"horizon": 5, "q_weight": 10.0, "r_weight": 1.0, "u_min": 0.0, "u_max": 0.05}
