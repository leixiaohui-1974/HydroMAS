"""Integration tests for MCP prediction server."""

import pytest

from mcp_servers.prediction_server import predict_future


class TestPredictFuture:
    def test_linear(self):
        data = [float(i) * 0.01 + 0.5 for i in range(100)]
        result = predict_future(historical_data=data, horizon=10, model="linear")
        assert len(result["predictions"]) == 10

    def test_polynomial(self):
        data = [float(i) * 0.01 + 0.5 for i in range(100)]
        result = predict_future(historical_data=data, horizon=10, model="polynomial")
        assert len(result["predictions"]) == 10

    def test_invalid_model(self):
        with pytest.raises(ValueError):
            predict_future([1.0, 2.0, 3.0], model="invalid")
