"""Integration tests for MCP evaluation server."""

import pytest
from mcp_servers.evaluation_server import evaluate_performance, assess_wnal


class TestEvaluatePerformance:
    def test_basic(self):
        obs = [1.0, 2.0, 3.0]
        pred = [1.1, 2.0, 2.9]
        result = evaluate_performance(observed=obs, predicted=pred)
        assert "RMSE" in result
        assert "MAE" in result
        assert "NSE" in result

    def test_with_setpoint(self):
        t = list(range(20))
        obs = [1.0] * 20
        pred = [0.5 + 0.025 * i for i in range(20)]
        result = evaluate_performance(
            observed=obs, predicted=pred,
            metrics=["RMSE", "overshoot", "settling_time"],
            time_series=t, setpoint=1.0,
        )
        assert "RMSE" in result


class TestAssessWNAL:
    def test_low_capabilities(self):
        caps = {"sensing": 10, "control": 10}
        result = assess_wnal(system_capabilities=caps)
        assert result["level"] in ("L0", "L1")

    def test_high_capabilities(self):
        caps = {k: 90 for k in [
            "sensing", "communication", "modeling",
            "prediction", "control", "odd_monitoring", "decision_support"
        ]}
        result = assess_wnal(system_capabilities=caps)
        assert result["level"] in ("L4", "L5")
