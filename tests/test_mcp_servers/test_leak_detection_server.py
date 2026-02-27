"""Integration tests for MCP leak detection server."""

import pytest

from mcp_servers.leak_detection_server import (
    build_network_graph,
    detect_leak,
    fuse_leak_evidence,
    localize_leak,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

def _sample_nodes():
    """Return a minimal list of valid node dicts."""
    return [
        {"id": "n1", "features": [1.0, 2.0, 0.01]},
        {"id": "n2", "features": [0.9, 1.8, 0.02]},
        {"id": "n3", "features": [1.1, 2.2, 0.03]},
    ]


def _sample_edges():
    """Return a minimal list of valid edge dicts."""
    return [
        {"source": "n1", "target": "n2", "features": [100.0, 0.3, 1]},
        {"source": "n2", "target": "n3", "features": [150.0, 0.25, 2]},
    ]


class TestBuildNetworkGraph:
    def test_build_network_graph(self):
        """Valid nodes and edges produce a graph dict."""
        result = build_network_graph(
            nodes=_sample_nodes(),
            edges=_sample_edges(),
        )
        assert isinstance(result, dict)
        assert "nodes" in result
        assert "edges" in result
        assert "adjacency" in result
        assert "n1" in result["nodes"]
        assert "n2" in result["nodes"]
        assert "n3" in result["nodes"]
        assert len(result["edges"]) == 2

    def test_build_network_graph_bad_node(self):
        """Node missing 'id' key raises ValueError."""
        bad_nodes = [
            {"features": [1.0, 2.0, 0.01]},  # missing 'id'
        ]
        with pytest.raises(ValueError, match="must have an 'id' key"):
            build_network_graph(nodes=bad_nodes, edges=[])


class TestDetectLeak:
    def test_detect_leak_normal(self):
        """Returns dict with expected keys from statistical fallback."""
        graph_data = build_network_graph(
            nodes=_sample_nodes(),
            edges=_sample_edges(),
        )
        result = detect_leak(graph_data=graph_data)
        assert isinstance(result, dict)
        assert "leak_detected" in result
        assert "anomaly_scores" in result
        assert "max_score" in result
        assert isinstance(result["leak_detected"], bool)
        assert isinstance(result["anomaly_scores"], dict)
        assert isinstance(result["max_score"], float)
        # All node ids should have scores
        for nid in ("n1", "n2", "n3"):
            assert nid in result["anomaly_scores"]


class TestLocalizeLeak:
    def test_localize_leak(self):
        """Returns dict with suspects list."""
        graph_data = build_network_graph(
            nodes=_sample_nodes(),
            edges=_sample_edges(),
        )
        anomaly_scores = {"n1": 0.9, "n2": 0.3, "n3": 0.7}
        result = localize_leak(
            graph_data=graph_data,
            anomaly_scores=anomaly_scores,
            top_k=2,
        )
        assert isinstance(result, dict)
        assert "suspects" in result
        assert "n_suspects" in result
        assert result["n_suspects"] <= 2
        assert len(result["suspects"]) == result["n_suspects"]
        # Each suspect should have the expected keys
        for suspect in result["suspects"]:
            assert "pipe_id" in suspect
            assert "confidence" in suspect
            assert "attention_weight" in suspect
            assert "connected_nodes" in suspect


class TestFuseLeakEvidence:
    def test_fuse_leak_evidence(self):
        """Matching acoustic and hydraulic evidence fuses correctly."""
        acoustic_events = [
            {
                "sensor_id": "s1",
                "timestamp": 100.0,
                "amplitude_db": 75.0,
                "frequency_hz": 500.0,
                "pipe_segment": "pipe_n1_n2",
            },
        ]
        hydraulic_suspects = [
            {
                "pipe_id": "pipe_n1_n2",
                "confidence": 0.85,
            },
        ]
        result = fuse_leak_evidence(
            acoustic_events=acoustic_events,
            hydraulic_suspects=hydraulic_suspects,
        )
        assert isinstance(result, dict)
        assert "fused_results" in result
        assert "n_results" in result
        assert result["n_results"] >= 1
        # The matching pipe should have both evidence sources
        fused = result["fused_results"]
        pipe_match = [r for r in fused if r["pipe_id"] == "pipe_n1_n2"]
        assert len(pipe_match) == 1
        assert "hydraulic_anomaly" in pipe_match[0]["evidence"]
        assert "acoustic_signature" in pipe_match[0]["evidence"]
        # Combined confidence should be higher than either alone
        assert pipe_match[0]["combined_confidence"] > 0.85

    def test_fuse_leak_evidence_empty(self):
        """Empty acoustic events and empty hydraulic suspects returns empty results."""
        result = fuse_leak_evidence(
            acoustic_events=[],
            hydraulic_suspects=[],
        )
        assert isinstance(result, dict)
        assert result["n_results"] == 0
        assert result["fused_results"] == []
