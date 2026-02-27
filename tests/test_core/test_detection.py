"""Tests for core.detection module.
core.detection 模块测试。
"""

import pytest
from core.detection.graph_builder import network_to_dict_graph, network_to_pyg_graph
from core.detection.gnn_leak import build_gat_model, detect_leak, localize_leak
from core.detection.acoustic_fusion import AcousticEvent, fuse_acoustic_hydraulic


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_nodes():
    """Return a small set of test nodes."""
    return [
        {"id": "N1", "features": [10.0, 2.5, 0.01]},
        {"id": "N2", "features": [8.0, 2.3, 0.02]},
        {"id": "N3", "features": [12.0, 2.7, 0.005]},
    ]


def _make_edges():
    """Return a small set of test edges."""
    return [
        {"source": "N1", "target": "N2", "features": [100.0, 0.3, 1]},
        {"source": "N2", "target": "N3", "features": [150.0, 0.25, 2]},
    ]


# ---------------------------------------------------------------------------
# Tests: graph_builder
# ---------------------------------------------------------------------------


class TestNetworkToDictGraph:
    def test_network_to_dict_graph(self):
        """Basic conversion with nodes and edges produces correct structure."""
        nodes = _make_nodes()
        edges = _make_edges()
        g = network_to_dict_graph(nodes, edges)

        assert "nodes" in g
        assert "edges" in g
        assert "adjacency" in g

        # Three nodes with correct features
        assert len(g["nodes"]) == 3
        assert g["nodes"]["N1"]["features"] == [10.0, 2.5, 0.01]
        assert g["nodes"]["N2"]["features"] == [8.0, 2.3, 0.02]
        assert g["nodes"]["N3"]["features"] == [12.0, 2.7, 0.005]

        # Two edges
        assert len(g["edges"]) == 2

        # Adjacency check
        assert "N2" in g["adjacency"]["N1"]
        assert "N3" in g["adjacency"]["N2"]

    def test_network_to_dict_graph_empty(self):
        """Empty inputs produce empty graph structures."""
        g = network_to_dict_graph([], [])
        assert g["nodes"] == {}
        assert g["edges"] == []
        assert g["adjacency"] == {}

    def test_network_to_dict_graph_single_node(self):
        """Single node with no edges produces valid graph."""
        nodes = [{"id": "A", "features": [1.0, 2.0, 3.0]}]
        g = network_to_dict_graph(nodes, [])
        assert len(g["nodes"]) == 1
        assert g["adjacency"]["A"] == []


class TestNetworkToPygGraph:
    def test_network_to_pyg_graph_no_torch(self, monkeypatch):
        """Without torch_geometric, raises ValueError."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("mock no torch")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        nodes = _make_nodes()
        edges = _make_edges()
        with pytest.raises(ValueError, match="torch not installed"):
            network_to_pyg_graph(nodes, edges)


# ---------------------------------------------------------------------------
# Tests: gnn_leak
# ---------------------------------------------------------------------------


class TestBuildGatModel:
    def test_build_gat_model_config(self):
        """Returns config dict with expected architecture keys."""
        config = build_gat_model()
        assert isinstance(config, dict)
        assert config["architecture"] == "GATv2"
        assert config["n_node_features"] == 3
        assert config["n_edge_features"] == 3
        assert config["hidden_dim"] == 64
        assert config["n_heads"] == 4
        assert config["output_dim"] == 1
        assert "layers" in config
        assert len(config["layers"]) == 3

    def test_build_gat_model_custom_params(self):
        """Custom parameters are reflected in the config."""
        config = build_gat_model(
            n_node_features=5,
            n_edge_features=2,
            hidden_dim=32,
            n_heads=2,
        )
        assert config["n_node_features"] == 5
        assert config["n_edge_features"] == 2
        assert config["hidden_dim"] == 32
        assert config["n_heads"] == 2


class TestDetectLeak:
    def test_detect_leak_no_leak(self):
        """Normal data with low variation should not trigger leak detection."""
        nodes = [
            {"id": "N1", "features": [10.0, 2.5, 0.01]},
            {"id": "N2", "features": [10.1, 2.5, 0.01]},
            {"id": "N3", "features": [9.9, 2.5, 0.01]},
            {"id": "N4", "features": [10.0, 2.5, 0.01]},
        ]
        edges = [
            {"source": "N1", "target": "N2", "features": [100.0, 0.3, 1]},
            {"source": "N2", "target": "N3", "features": [100.0, 0.3, 1]},
            {"source": "N3", "target": "N4", "features": [100.0, 0.3, 1]},
        ]
        g = network_to_dict_graph(nodes, edges)
        result = detect_leak(g)

        assert "leak_detected" in result
        assert "anomaly_scores" in result
        assert "max_score" in result
        assert result["leak_detected"] is False

    def test_detect_leak_with_anomaly(self):
        """One extreme outlier node should trigger leak detection."""
        # Create a set of normal nodes and one extreme outlier
        nodes = [
            {"id": "N1", "features": [10.0, 2.5, 0.01]},
            {"id": "N2", "features": [10.0, 2.5, 0.01]},
            {"id": "N3", "features": [10.0, 2.5, 0.01]},
            {"id": "N4", "features": [10.0, 2.5, 0.01]},
            # Extreme outlier -- much higher flow, low pressure, high residual
            {"id": "N5", "features": [500.0, 0.01, 50.0]},
        ]
        edges = [
            {"source": "N1", "target": "N2", "features": [100.0, 0.3, 1]},
            {"source": "N2", "target": "N3", "features": [100.0, 0.3, 1]},
            {"source": "N3", "target": "N4", "features": [100.0, 0.3, 1]},
            {"source": "N4", "target": "N5", "features": [100.0, 0.3, 1]},
        ]
        g = network_to_dict_graph(nodes, edges)
        # Statistical fallback uses sigmoid(mean_z - 2) which caps ~0.45 for outlier;
        # use a threshold below that to detect the anomaly
        result = detect_leak(g, threshold=0.4)

        assert result["leak_detected"] is True
        assert result["max_score"] >= 0.4
        # The outlier node should have the highest score
        assert result["anomaly_scores"]["N5"] == result["max_score"]

    def test_detect_leak_returns_all_node_scores(self):
        """All nodes should appear in the anomaly_scores dict."""
        nodes = _make_nodes()
        edges = _make_edges()
        g = network_to_dict_graph(nodes, edges)
        result = detect_leak(g)
        for n in nodes:
            assert str(n["id"]) in result["anomaly_scores"]


class TestLocalizeLeak:
    def test_localize_leak(self):
        """Returns top_k results, each with expected keys."""
        nodes = _make_nodes()
        edges = _make_edges()
        g = network_to_dict_graph(nodes, edges)

        # Create mock anomaly scores
        anomaly_scores = {"N1": 0.3, "N2": 0.9, "N3": 0.1}
        results = localize_leak(g, anomaly_scores, top_k=2)

        assert isinstance(results, list)
        assert len(results) <= 2

        for r in results:
            assert "pipe_id" in r
            assert "confidence" in r
            assert "attention_weight" in r
            assert "connected_nodes" in r

        # First result should have the highest confidence
        if len(results) >= 2:
            assert results[0]["confidence"] >= results[1]["confidence"]

    def test_localize_leak_ordering(self):
        """Results are sorted by confidence descending."""
        nodes = [
            {"id": "A", "features": [1.0, 1.0, 1.0]},
            {"id": "B", "features": [2.0, 2.0, 2.0]},
            {"id": "C", "features": [3.0, 3.0, 3.0]},
        ]
        edges = [
            {"source": "A", "target": "B", "features": [10.0, 0.1, 1]},
            {"source": "B", "target": "C", "features": [20.0, 0.2, 2]},
        ]
        g = network_to_dict_graph(nodes, edges)
        anomaly_scores = {"A": 0.1, "B": 0.5, "C": 0.95}
        results = localize_leak(g, anomaly_scores, top_k=3)

        # Pipe B->C should come first (max of 0.5, 0.95 = 0.95)
        assert results[0]["pipe_id"] == "pipe_B_C"
        assert results[0]["confidence"] == 0.95

    def test_localize_leak_empty_graph(self):
        """Empty graph produces empty localization results."""
        g = network_to_dict_graph([], [])
        results = localize_leak(g, {}, top_k=3)
        assert results == []


# ---------------------------------------------------------------------------
# Tests: acoustic_fusion
# ---------------------------------------------------------------------------


class TestAcousticEvent:
    def test_acoustic_event_defaults(self):
        """AcousticEvent dataclass has correct default values."""
        evt = AcousticEvent()
        assert evt.sensor_id == ""
        assert evt.timestamp == 0.0
        assert evt.amplitude_db == 0.0
        assert evt.frequency_hz == 0.0
        assert evt.pipe_segment == ""

    def test_acoustic_event_validate_good(self):
        """Valid AcousticEvent passes validation."""
        evt = AcousticEvent(
            sensor_id="S1",
            timestamp=100.0,
            amplitude_db=75.0,
            frequency_hz=1200.0,
            pipe_segment="pipe_N1_N2",
        )
        evt.validate()  # should not raise

    def test_acoustic_event_validate_bad_amplitude(self):
        """Negative amplitude raises ValueError."""
        evt = AcousticEvent(amplitude_db=-10.0)
        with pytest.raises(ValueError, match="Amplitude must be >= 0"):
            evt.validate()

    def test_acoustic_event_validate_bad_frequency(self):
        """Negative frequency raises ValueError."""
        evt = AcousticEvent(frequency_hz=-500.0)
        with pytest.raises(ValueError, match="Frequency must be >= 0"):
            evt.validate()


class TestFuseAcousticHydraulic:
    def test_fuse_acoustic_hydraulic(self):
        """Fusion with matching pipe segments produces combined confidence."""
        acoustic_events = [
            AcousticEvent(
                sensor_id="S1",
                timestamp=100.0,
                amplitude_db=80.0,
                frequency_hz=1200.0,
                pipe_segment="pipe_N1_N2",
            ),
        ]
        hydraulic_suspects = [
            {"pipe_id": "pipe_N1_N2", "confidence": 0.85},
            {"pipe_id": "pipe_N2_N3", "confidence": 0.40},
        ]
        results = fuse_acoustic_hydraulic(acoustic_events, hydraulic_suspects)

        assert isinstance(results, list)
        assert len(results) >= 1

        # Find the pipe with both evidence sources
        matched = [r for r in results if r["pipe_id"] == "pipe_N1_N2"]
        assert len(matched) == 1
        r = matched[0]
        assert "combined_confidence" in r
        assert "evidence" in r
        assert "hydraulic_anomaly" in r["evidence"]
        assert "acoustic_signature" in r["evidence"]

        # Combined confidence should be higher than either alone
        # Bayesian: combined = 1 - (1-0.85)*(1 - 80/(80+60)) = 1 - 0.15 * (1 - 0.5714...)
        p_h = 0.85
        p_a = 80.0 / (80.0 + 60.0)
        expected_combined = 1.0 - (1.0 - p_h) * (1.0 - p_a)
        assert abs(r["combined_confidence"] - round(expected_combined, 6)) < 1e-6

    def test_fuse_acoustic_hydraulic_no_overlap(self):
        """Non-overlapping pipe IDs produce separate results."""
        acoustic_events = [
            AcousticEvent(
                sensor_id="S1",
                amplitude_db=70.0,
                frequency_hz=1000.0,
                pipe_segment="pipe_A_B",
            ),
        ]
        hydraulic_suspects = [
            {"pipe_id": "pipe_C_D", "confidence": 0.6},
        ]
        results = fuse_acoustic_hydraulic(acoustic_events, hydraulic_suspects)
        assert len(results) == 2
        pipe_ids = {r["pipe_id"] for r in results}
        assert "pipe_A_B" in pipe_ids
        assert "pipe_C_D" in pipe_ids

    def test_fuse_acoustic_hydraulic_empty(self):
        """Empty inputs produce empty results."""
        results = fuse_acoustic_hydraulic([], [])
        assert results == []

    def test_fuse_acoustic_hydraulic_sorted_by_confidence(self):
        """Results are sorted by combined_confidence descending."""
        acoustic_events = [
            AcousticEvent(sensor_id="S1", amplitude_db=90.0, pipe_segment="pipe_A_B"),
            AcousticEvent(sensor_id="S2", amplitude_db=30.0, pipe_segment="pipe_C_D"),
        ]
        hydraulic_suspects = [
            {"pipe_id": "pipe_A_B", "confidence": 0.9},
            {"pipe_id": "pipe_C_D", "confidence": 0.2},
        ]
        results = fuse_acoustic_hydraulic(acoustic_events, hydraulic_suspects)
        assert len(results) == 2
        assert results[0]["combined_confidence"] >= results[1]["combined_confidence"]

    def test_fuse_acoustic_hydraulic_invalid_event(self):
        """Invalid acoustic event amplitude raises ValueError."""
        acoustic_events = [
            AcousticEvent(sensor_id="S1", amplitude_db=-5.0, pipe_segment="pipe_X_Y"),
        ]
        hydraulic_suspects = []
        with pytest.raises(ValueError, match="Amplitude must be >= 0"):
            fuse_acoustic_hydraulic(acoustic_events, hydraulic_suspects)
