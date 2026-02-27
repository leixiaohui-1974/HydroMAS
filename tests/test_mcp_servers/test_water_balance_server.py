"""Integration tests for MCP water balance server."""

import pytest

from mcp_servers.water_balance_server import (
    calc_full_plant_balance,
    calc_node_balance,
    detect_balance_anomaly,
)


class TestCalcNodeBalance:
    def test_calc_node_balance_normal(self):
        """Valid node data returns dict with residual."""
        result = calc_node_balance(
            node_id="pool_1",
            node_type="pool",
            q_in=1.0,
            q_out=0.8,
            q_loss=0.05,
            q_evap=0.02,
            volume=10.0,
            capacity=100.0,
        )
        assert isinstance(result, dict)
        assert "residual" in result
        assert "is_balanced" in result
        assert result["node_id"] == "pool_1"
        assert result["node_type"] == "pool"
        # residual = 1.0 - 0.8 - 0.05 - 0.02 - 0.0 = 0.13
        assert abs(result["residual"] - 0.13) < 1e-9

    def test_calc_node_balance_balanced(self):
        """q_in == q_out (with zero losses) produces residual near 0."""
        result = calc_node_balance(
            node_id="intake_1",
            node_type="intake",
            q_in=0.5,
            q_out=0.5,
        )
        assert abs(result["residual"]) < 1e-9
        assert result["is_balanced"] is True

    def test_calc_node_balance_invalid(self):
        """Negative flow raises ValueError."""
        with pytest.raises(ValueError):
            calc_node_balance(
                node_id="pool_1",
                node_type="pool",
                q_in=-1.0,
                q_out=0.5,
            )


class TestCalcFullPlantBalance:
    def test_calc_full_plant_balance(self):
        """Multiple nodes and edges returns plant-wide balance dict."""
        nodes_data = [
            {
                "node_id": "intake_1",
                "node_type": "intake",
                "q_in": 1.0,
                "q_out": 1.0,
            },
            {
                "node_id": "workshop_1",
                "node_type": "workshop",
                "q_in": 0.6,
                "q_out": 0.5,
                "q_loss": 0.05,
                "q_evap": 0.05,
            },
            {
                "node_id": "reuse_1",
                "node_type": "reuse",
                "q_in": 0.4,
                "q_out": 0.4,
            },
        ]
        edges_data = [
            ["intake_1", "workshop_1"],
            ["intake_1", "reuse_1"],
        ]
        result = calc_full_plant_balance(
            nodes_data=nodes_data,
            edges_data=edges_data,
        )
        assert isinstance(result, dict)
        assert "node_residuals" in result
        assert "total_intake" in result
        assert "total_consumption" in result
        assert "total_loss" in result
        assert "total_evap" in result
        assert "reuse_rate" in result
        assert "balance_error" in result
        assert result["total_intake"] == pytest.approx(1.0)
        assert result["total_loss"] == pytest.approx(0.05)
        assert result["total_evap"] == pytest.approx(0.05)

    def test_calc_full_plant_balance_empty(self):
        """Empty nodes list raises ValueError."""
        with pytest.raises(ValueError, match="nodes_data list cannot be empty"):
            calc_full_plant_balance(nodes_data=[], edges_data=[])


class TestDetectBalanceAnomaly:
    def test_detect_balance_anomaly_none(self):
        """All residuals within threshold produces no anomalies."""
        residuals = {
            "node_A": 0.01,
            "node_B": -0.02,
            "node_C": 0.005,
        }
        result = detect_balance_anomaly(residuals=residuals, threshold=0.03)
        assert isinstance(result, dict)
        assert "anomalies" in result
        assert "n_anomalies" in result
        assert result["n_anomalies"] == 0
        assert len(result["anomalies"]) == 0

    def test_detect_balance_anomaly_found(self):
        """Residuals above threshold are flagged as anomalies."""
        residuals = {
            "node_A": 0.01,
            "node_B": -0.15,
            "node_C": 0.08,
        }
        result = detect_balance_anomaly(residuals=residuals, threshold=0.03)
        assert result["n_anomalies"] == 2
        assert len(result["anomalies"]) == 2
        assert "classification" in result
        # Classification should have the standard keys
        classification = result["classification"]
        assert "leak" in classification
        assert "meter_error" in classification
        assert "process_change" in classification
