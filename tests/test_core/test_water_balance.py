"""Tests for core.water_balance module.
core.water_balance 模块测试。
"""

import pytest

from core.water_balance.balance_graph import (
    build_balance_graph,
    calc_full_balance,
    get_graph_summary,
)
from core.water_balance.node_balance import BalanceNode, calc_node_residual, calc_reuse_rate
from core.water_balance.residual_calc import calc_rolling_residual, classify_anomaly, detect_anomaly

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_simple_nodes():
    """Create a small set of BalanceNode instances for graph tests."""
    intake = BalanceNode(
        node_id="intake1", node_type="intake",
        q_in=1.0, q_out=0.8, q_loss=0.1, q_evap=0.05,
        volume=100.0, capacity=500.0,
    )
    pool = BalanceNode(
        node_id="pool1", node_type="pool",
        q_in=0.8, q_out=0.7, q_loss=0.05, q_evap=0.02,
        volume=50.0, capacity=200.0,
    )
    reuse = BalanceNode(
        node_id="reuse1", node_type="reuse",
        q_in=0.3, q_out=0.3, q_loss=0.0, q_evap=0.0,
        volume=10.0, capacity=50.0,
    )
    return [intake, pool, reuse]


def _make_simple_edges():
    """Create edges for the simple node set."""
    return [("intake1", "pool1"), ("pool1", "reuse1")]


# ---------------------------------------------------------------------------
# BalanceNode
# ---------------------------------------------------------------------------

class TestBalanceNodeDefaults:
    def test_balance_node_defaults(self):
        """BalanceNode should initialise with zero flow and volume defaults."""
        node = BalanceNode(node_id="n1", node_type="intake")
        assert node.node_id == "n1"
        assert node.node_type == "intake"
        assert node.q_in == 0.0
        assert node.q_out == 0.0
        assert node.q_loss == 0.0
        assert node.q_evap == 0.0
        assert node.volume == 0.0
        assert node.capacity == 0.0


class TestBalanceNodeValidation:
    def test_balance_node_validate_good(self):
        """Valid BalanceNode should not raise on validate()."""
        node = BalanceNode(
            node_id="n1", node_type="pool",
            q_in=1.0, q_out=0.5, q_loss=0.1, q_evap=0.05,
            volume=10.0, capacity=100.0,
        )
        node.validate()  # should not raise

    def test_balance_node_validate_bad_flow(self):
        """Negative q_in should raise ValueError."""
        node = BalanceNode(node_id="n1", node_type="intake", q_in=-0.5)
        with pytest.raises(ValueError, match="q_in"):
            node.validate()

    def test_balance_node_validate_bad_q_out(self):
        """Negative q_out should raise ValueError."""
        node = BalanceNode(node_id="n1", node_type="intake", q_out=-1.0)
        with pytest.raises(ValueError, match="q_out"):
            node.validate()

    def test_balance_node_validate_bad_node_type(self):
        """Invalid node_type should raise ValueError."""
        node = BalanceNode(node_id="n1", node_type="invalid")
        with pytest.raises(ValueError, match="node_type"):
            node.validate()

    def test_balance_node_validate_capacity_less_than_volume(self):
        """capacity < volume should raise ValueError."""
        node = BalanceNode(
            node_id="n1", node_type="pool",
            volume=100.0, capacity=50.0,
        )
        with pytest.raises(ValueError, match="capacity"):
            node.validate()


# ---------------------------------------------------------------------------
# calc_node_residual
# ---------------------------------------------------------------------------

class TestCalcNodeResidual:
    def test_calc_node_residual_balanced(self):
        """When q_in equals q_out (no loss/evap), residual should be ~0."""
        node = BalanceNode(
            node_id="n1", node_type="pool",
            q_in=1.0, q_out=1.0, q_loss=0.0, q_evap=0.0,
        )
        residual = calc_node_residual(node)
        assert abs(residual) < 1e-12

    def test_calc_node_residual_imbalanced(self):
        """When q_in > q_out + losses, residual should be positive."""
        node = BalanceNode(
            node_id="n1", node_type="pool",
            q_in=2.0, q_out=1.0, q_loss=0.1, q_evap=0.05,
        )
        residual = calc_node_residual(node)
        # R = 2.0 - 1.0 - 0.1 - 0.05 - 0 = 0.85
        assert abs(residual - 0.85) < 1e-12

    def test_calc_node_residual_with_dvdt(self):
        """dv_dt should be subtracted from the residual."""
        node = BalanceNode(
            node_id="n1", node_type="pool",
            q_in=1.0, q_out=0.5, q_loss=0.0, q_evap=0.0,
        )
        # R = 1.0 - 0.5 - 0.0 - 0.0 - 0.3 = 0.2
        residual = calc_node_residual(node, dv_dt=0.3)
        assert abs(residual - 0.2) < 1e-12

    def test_calc_node_residual_negative(self):
        """When q_out > q_in, residual should be negative."""
        node = BalanceNode(
            node_id="n1", node_type="pool",
            q_in=0.5, q_out=1.0, q_loss=0.0, q_evap=0.0,
        )
        residual = calc_node_residual(node)
        assert residual < 0


# ---------------------------------------------------------------------------
# calc_reuse_rate
# ---------------------------------------------------------------------------

class TestCalcReuseRate:
    def test_calc_reuse_rate_normal(self):
        """Normal reuse rate calculation."""
        rate = calc_reuse_rate(0.3, 1.0)
        assert abs(rate - 0.3) < 1e-12

    def test_calc_reuse_rate_zero_intake(self):
        """Zero intake should return 0.0 (avoid division by zero)."""
        rate = calc_reuse_rate(0.5, 0.0)
        assert rate == 0.0

    def test_calc_reuse_rate_negative_intake(self):
        """Negative intake should return 0.0."""
        rate = calc_reuse_rate(0.5, -1.0)
        assert rate == 0.0

    def test_calc_reuse_rate_capped_at_one(self):
        """Reuse rate should be capped at 1.0."""
        rate = calc_reuse_rate(2.0, 1.0)
        assert rate == 1.0


# ---------------------------------------------------------------------------
# build_balance_graph
# ---------------------------------------------------------------------------

class TestBuildBalanceGraph:
    def test_build_balance_graph(self):
        """Build a graph with a few nodes and edges and verify structure."""
        nodes = _make_simple_nodes()
        edges = _make_simple_edges()
        graph = build_balance_graph(nodes, edges)
        # Whether networkx or dict, the graph should be usable
        assert graph is not None

    def test_build_balance_graph_bad_edge_source(self):
        """Edge referencing a non-existent source should raise ValueError."""
        nodes = _make_simple_nodes()
        edges = [("nonexistent", "pool1")]
        with pytest.raises(ValueError, match="source"):
            build_balance_graph(nodes, edges)

    def test_build_balance_graph_bad_edge_dest(self):
        """Edge referencing a non-existent destination should raise ValueError."""
        nodes = _make_simple_nodes()
        edges = [("intake1", "nonexistent")]
        with pytest.raises(ValueError, match="destination"):
            build_balance_graph(nodes, edges)


# ---------------------------------------------------------------------------
# calc_full_balance
# ---------------------------------------------------------------------------

class TestCalcFullBalance:
    def test_calc_full_balance(self):
        """Full balance should produce expected keys and correct totals."""
        nodes = _make_simple_nodes()
        edges = _make_simple_edges()
        graph = build_balance_graph(nodes, edges)
        result = calc_full_balance(graph)

        assert "node_residuals" in result
        assert "total_intake" in result
        assert "total_consumption" in result
        assert "total_loss" in result
        assert "total_evap" in result
        assert "reuse_rate" in result
        assert "balance_error" in result

        # intake1 has q_in=1.0 and is type "intake"
        assert abs(result["total_intake"] - 1.0) < 1e-12

        # reuse1 has q_in=0.3 and is type "reuse"
        # reuse_rate = min(0.3 / 1.0, 1.0) = 0.3
        assert abs(result["reuse_rate"] - 0.3) < 1e-12

        # total_consumption = sum of q_out = 0.8 + 0.7 + 0.3 = 1.8
        assert abs(result["total_consumption"] - 1.8) < 1e-12

        # total_loss = 0.1 + 0.05 + 0.0 = 0.15
        assert abs(result["total_loss"] - 0.15) < 1e-12

        # total_evap = 0.05 + 0.02 + 0.0 = 0.07
        assert abs(result["total_evap"] - 0.07) < 1e-12

    def test_calc_full_balance_balanced_nodes(self):
        """Perfectly balanced nodes should have near-zero balance_error."""
        node = BalanceNode(
            node_id="n1", node_type="intake",
            q_in=1.0, q_out=1.0, q_loss=0.0, q_evap=0.0,
        )
        graph = build_balance_graph([node], [])
        result = calc_full_balance(graph)
        assert abs(result["balance_error"]) < 1e-12


# ---------------------------------------------------------------------------
# get_graph_summary
# ---------------------------------------------------------------------------

class TestGetGraphSummary:
    def test_get_graph_summary(self):
        """Summary should report correct counts and totals."""
        nodes = _make_simple_nodes()
        edges = _make_simple_edges()
        graph = build_balance_graph(nodes, edges)
        summary = get_graph_summary(graph)

        assert summary["n_nodes"] == 3
        assert summary["n_edges"] == 2
        assert summary["node_types_count"]["intake"] == 1
        assert summary["node_types_count"]["pool"] == 1
        assert summary["node_types_count"]["reuse"] == 1
        assert abs(summary["total_intake"] - 1.0) < 1e-12
        # total_consumption = sum of q_out = 0.8 + 0.7 + 0.3 = 1.8
        assert abs(summary["total_consumption"] - 1.8) < 1e-12


# ---------------------------------------------------------------------------
# detect_anomaly
# ---------------------------------------------------------------------------

class TestDetectAnomaly:
    def test_detect_anomaly_none(self):
        """All residuals within threshold should produce empty anomaly list."""
        residuals = {"n1": 0.01, "n2": -0.02, "n3": 0.005}
        anomalies = detect_anomaly(residuals, threshold=0.03)
        assert anomalies == []

    def test_detect_anomaly_found(self):
        """Residuals above threshold should be detected."""
        residuals = {"n1": 0.01, "n2": 0.15, "n3": -0.08}
        anomalies = detect_anomaly(residuals, threshold=0.03)
        detected_ids = {a["node_id"] for a in anomalies}
        assert "n2" in detected_ids
        assert "n3" in detected_ids
        assert "n1" not in detected_ids

    def test_detect_anomaly_severity_high(self):
        """Residual >= 0.10 should be classified as high severity."""
        residuals = {"n1": 0.15}
        anomalies = detect_anomaly(residuals, threshold=0.03)
        assert len(anomalies) == 1
        assert anomalies[0]["severity"] == "high"

    def test_detect_anomaly_severity_medium(self):
        """Residual in [0.05, 0.10) should be classified as medium severity."""
        residuals = {"n1": 0.07}
        anomalies = detect_anomaly(residuals, threshold=0.03)
        assert len(anomalies) == 1
        assert anomalies[0]["severity"] == "medium"

    def test_detect_anomaly_severity_low(self):
        """Residual in [threshold, 0.05) should be classified as low severity."""
        residuals = {"n1": 0.04}
        anomalies = detect_anomaly(residuals, threshold=0.03)
        assert len(anomalies) == 1
        assert anomalies[0]["severity"] == "low"

    def test_detect_anomaly_sorted_descending(self):
        """Anomalies should be sorted by descending absolute residual."""
        residuals = {"n1": 0.05, "n2": 0.20, "n3": -0.10}
        anomalies = detect_anomaly(residuals, threshold=0.03)
        abs_vals = [abs(a["residual"]) for a in anomalies]
        assert abs_vals == sorted(abs_vals, reverse=True)

    def test_detect_anomaly_negative_threshold(self):
        """Negative threshold should raise ValueError."""
        with pytest.raises(ValueError, match="threshold"):
            detect_anomaly({"n1": 0.1}, threshold=-0.01)


# ---------------------------------------------------------------------------
# calc_rolling_residual
# ---------------------------------------------------------------------------

class TestCalcRollingResidual:
    def test_calc_rolling_residual(self):
        """Rolling residual should compute moving averages correctly."""
        time_series = [
            {"n1": 1.0},
            {"n1": 2.0},
            {"n1": 3.0},
            {"n1": 4.0},
            {"n1": 5.0},
        ]
        result = calc_rolling_residual(time_series, window=3)
        # For n1 with window=3:
        # avg(1,2,3)=2.0, avg(2,3,4)=3.0, avg(3,4,5)=4.0
        assert "n1" in result
        assert len(result["n1"]) == 3
        assert abs(result["n1"][0] - 2.0) < 1e-12
        assert abs(result["n1"][1] - 3.0) < 1e-12
        assert abs(result["n1"][2] - 4.0) < 1e-12

    def test_calc_rolling_residual_window_larger_than_series(self):
        """Window > time_series length should return empty lists."""
        time_series = [{"n1": 1.0}, {"n1": 2.0}]
        result = calc_rolling_residual(time_series, window=5)
        assert result["n1"] == []

    def test_calc_rolling_residual_empty_series(self):
        """Empty time series should return empty dict."""
        result = calc_rolling_residual([], window=3)
        assert result == {}

    def test_calc_rolling_residual_bad_window(self):
        """Non-positive window should raise ValueError."""
        with pytest.raises(ValueError, match="window"):
            calc_rolling_residual([{"n1": 1.0}], window=0)

    def test_calc_rolling_residual_multiple_nodes(self):
        """Rolling residual should work for multiple nodes independently."""
        time_series = [
            {"n1": 1.0, "n2": 10.0},
            {"n1": 3.0, "n2": 20.0},
            {"n1": 5.0, "n2": 30.0},
        ]
        result = calc_rolling_residual(time_series, window=2)
        # n1: avg(1,3)=2.0, avg(3,5)=4.0
        assert len(result["n1"]) == 2
        assert abs(result["n1"][0] - 2.0) < 1e-12
        assert abs(result["n1"][1] - 4.0) < 1e-12
        # n2: avg(10,20)=15.0, avg(20,30)=25.0
        assert len(result["n2"]) == 2
        assert abs(result["n2"][0] - 15.0) < 1e-12
        assert abs(result["n2"][1] - 25.0) < 1e-12


# ---------------------------------------------------------------------------
# classify_anomaly
# ---------------------------------------------------------------------------

class TestClassifyAnomaly:
    def test_classify_anomaly(self):
        """Classification should sort anomalies into leak/meter_error/process_change."""
        anomalies = [
            {"node_id": "n1", "residual": -0.15, "relative_error": 0.15, "severity": "high"},
            {"node_id": "n2", "residual": 0.12, "relative_error": 0.12, "severity": "high"},
            {"node_id": "n3", "residual": -0.06, "relative_error": 0.06, "severity": "medium"},
            {"node_id": "n4", "residual": 0.04, "relative_error": 0.04, "severity": "low"},
        ]
        classified = classify_anomaly(anomalies)

        # n1: high severity + negative residual -> leak
        leak_ids = {a["node_id"] for a in classified["leak"]}
        assert "n1" in leak_ids
        # n3: medium severity + negative residual -> leak
        assert "n3" in leak_ids

        # n2: high severity + positive residual -> process_change
        pc_ids = {a["node_id"] for a in classified["process_change"]}
        assert "n2" in pc_ids

        # n4: low severity + positive residual -> meter_error
        me_ids = {a["node_id"] for a in classified["meter_error"]}
        assert "n4" in me_ids

    def test_classify_anomaly_empty(self):
        """Empty anomaly list should return empty categories."""
        classified = classify_anomaly([])
        assert classified["leak"] == []
        assert classified["meter_error"] == []
        assert classified["process_change"] == []

    def test_classify_anomaly_all_leaks(self):
        """All high-severity negative anomalies should be classified as leaks."""
        anomalies = [
            {"node_id": "n1", "residual": -0.20, "relative_error": 0.20, "severity": "high"},
            {"node_id": "n2", "residual": -0.15, "relative_error": 0.15, "severity": "high"},
        ]
        classified = classify_anomaly(anomalies)
        assert len(classified["leak"]) == 2
        assert len(classified["process_change"]) == 0
        assert len(classified["meter_error"]) == 0
