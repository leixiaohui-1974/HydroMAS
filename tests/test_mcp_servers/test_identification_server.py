"""Integration tests for MCP identification server."""

import numpy as np

from core.simulation.tank_model import GRAVITY
from mcp_servers.identification_server import identify_parameters


class TestIdentifyParameters:
    def test_nonlinear(self):
        h = np.linspace(0.2, 1.5, 50)
        q = 0.6 * 0.01 * np.sqrt(2 * GRAVITY * h)
        result = identify_parameters(
            observed_h=h.tolist(),
            observed_q_out=q.tolist(),
            model_type="nonlinear",
        )
        assert result["converged"]
        assert abs(result["cd"] - 0.6) < 0.1

    def test_arx(self):
        n = 100
        u = [0.01] * n
        y = [0.0] * n
        for i in range(1, n):
            y[i] = 0.9 * y[i - 1] + 0.2 * u[i - 1]
        result = identify_parameters(
            observed_h=y,
            observed_q_out=u,
            model_type="ARX",
            arx_config={"u": u, "na": 1, "nb": 1},
        )
        assert result["r_squared"] > 0.8
