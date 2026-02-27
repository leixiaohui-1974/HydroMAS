"""Integration tests for LeakDiagnosisSkill (泄漏诊断)."""

import pytest

from skills.leak_diagnosis import LeakDiagnosisSkill

# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

def _nodes_data():
    return [
        {
            "node_id": "n1", "node_type": "intake",
            "q_in": 100, "q_out": 95, "q_loss": 0, "q_evap": 0,
        },
        {
            "node_id": "n2", "node_type": "workshop",
            "q_in": 95, "q_out": 90, "q_loss": 2, "q_evap": 0,
        },
    ]


def _edges_data():
    return [["n1", "n2"]]


def _graph_nodes():
    return [
        {"id": "n1", "features": [100, 0.3, 0.01]},
        {"id": "n2", "features": [90, 0.25, 0.05]},
    ]


def _graph_edges():
    return [
        {"source": "n1", "target": "n2", "features": [500, 0.3, 1]},
    ]


def _acoustic_data():
    return [
        {
            "sensor_id": "s1",
            "timestamp": 100.0,
            "amplitude_db": 60.0,
            "frequency_hz": 1500.0,
            "pipe_segment": "pipe_n1_n2",
        },
    ]


# ---------------------------------------------------------------------------
# Mock tool functions that match the parameter names the skill sends
# ---------------------------------------------------------------------------

def _mock_calc_full_plant_balance(nodes_data, edges_data):
    return {
        "total_input": 100.0,
        "total_output": 90.0,
        "residual": 10.0,
        "node_residuals": {"n1": 5.0, "n2": 3.0},
    }


def _mock_detect_balance_anomaly(balance_data):
    return {
        "anomalies": [{"node": "n2", "description": "Residual too high"}],
        "classification": {"leak": ["n2"]},
        "n_anomalies": 1,
    }


def _mock_detect_leak(graph_nodes, graph_edges):
    return {
        "leak_detected": True,
        "leak_scores": [0.9, 0.3],
        "anomaly_scores": {"n1": 0.2, "n2": 0.9},
        "max_score": 0.9,
    }


def _mock_localize_leak(graph_nodes, graph_edges, leak_scores):
    return {
        "candidates": [
            {"pipe_id": "pipe_n1_n2", "confidence": 0.85, "connected_nodes": ["n1", "n2"]},
        ],
        "n_suspects": 1,
    }


def _mock_fuse_leak_evidence(leak_candidates, acoustic_data):
    return {
        "fused_candidates": [
            {"pipe_id": "pipe_n1_n2", "combined_confidence": 0.92},
        ],
        "n_results": 1,
    }


def _build_skill():
    """Create a LeakDiagnosisSkill with all tools mocked."""
    skill = LeakDiagnosisSkill()
    skill.register_tool("calc_full_plant_balance", _mock_calc_full_plant_balance)
    skill.register_tool("detect_balance_anomaly", _mock_detect_balance_anomaly)
    skill.register_tool("detect_leak", _mock_detect_leak)
    skill.register_tool("localize_leak", _mock_localize_leak)
    skill.register_tool("fuse_leak_evidence", _mock_fuse_leak_evidence)
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLeakDiagnosis:
    @pytest.mark.asyncio
    async def test_leak_diagnosis_init(self):
        """LeakDiagnosisSkill can be instantiated and has an execute method."""
        skill = LeakDiagnosisSkill()
        assert hasattr(skill, "execute")
        assert callable(skill.execute)

    @pytest.mark.asyncio
    async def test_leak_diagnosis_execute(self):
        """Full execution with sample data returns success and expected keys."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
            "graph_nodes": _graph_nodes(),
            "graph_edges": _graph_edges(),
        })
        assert result.success
        assert "diagnosis" in result.data
        assert "balance" in result.data
        assert "anomalies" in result.data
        assert "leak_detection" in result.data
        assert "localization" in result.data
        assert result.data["diagnosis"]["has_leak"] is True

    @pytest.mark.asyncio
    async def test_leak_diagnosis_no_data(self):
        """Missing required params returns SkillResult with success=False."""
        skill = _build_skill()
        # No nodes_data or edges_data
        result = await skill.run({})
        assert not result.success
        assert "nodes_data" in result.error or "edges_data" in result.error

    @pytest.mark.asyncio
    async def test_leak_diagnosis_with_acoustic(self):
        """Include acoustic_data triggers the acoustic fusion step."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
            "graph_nodes": _graph_nodes(),
            "graph_edges": _graph_edges(),
            "acoustic_data": _acoustic_data(),
        })
        assert result.success
        assert "acoustic_fusion" in result.steps_completed
        assert result.data["acoustic_fusion"] != {}

    @pytest.mark.asyncio
    async def test_leak_diagnosis_steps(self):
        """Verify steps_completed list for a full run without acoustic data."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
            "graph_nodes": _graph_nodes(),
            "graph_edges": _graph_edges(),
        })
        assert result.success
        assert result.steps_completed == [
            "water_balance",
            "anomaly_detection",
            "gnn_leak_detection",
            "leak_localization",
        ]

    @pytest.mark.asyncio
    async def test_leak_diagnosis_no_leak(self):
        """When no leak is detected the diagnosis severity should be low or medium."""
        def mock_detect_no_leak(graph_nodes, graph_edges):
            return {
                "leak_detected": False,
                "leak_scores": [0.1, 0.05],
                "anomaly_scores": {"n1": 0.1, "n2": 0.05},
                "max_score": 0.1,
            }

        def mock_anomaly_none(balance_data):
            return {"anomalies": [], "classification": {}, "n_anomalies": 0}

        skill = _build_skill()
        skill.register_tool("detect_leak", mock_detect_no_leak)
        skill.register_tool("detect_balance_anomaly", mock_anomaly_none)
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
            "graph_nodes": _graph_nodes(),
            "graph_edges": _graph_edges(),
        })
        assert result.success
        assert result.data["diagnosis"]["severity"] == "low"

    @pytest.mark.asyncio
    async def test_leak_diagnosis_execution_time(self):
        """Execution time is recorded and positive."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
            "graph_nodes": _graph_nodes(),
            "graph_edges": _graph_edges(),
        })
        assert result.execution_time > 0
