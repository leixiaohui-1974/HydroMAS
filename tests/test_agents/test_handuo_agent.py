"""Phase 3 tests for the Handuo Water Network LLM Agent.
Phase 3 瀚铎水网大模型 Agent 测试。

Tests cover initialization, RAG-based Q&A (template fallback mode),
anomaly diagnosis, insight generation, and no-LLM fallback behavior.
"""

import pytest

from agents.handuo_agent import HanduoAgent


class TestHanduoAgent:
    """Test HanduoAgent template-mode behavior."""

    def setup_method(self):
        self.agent = HanduoAgent()

    def test_handuo_init(self):
        """HanduoAgent should initialize without error."""
        agent = HanduoAgent()
        assert agent._llm is None
        assert isinstance(agent._knowledge, dict)
        # Knowledge base should have loaded entities and fault_modes
        assert "entities" in agent._knowledge
        assert "fault_modes" in agent._knowledge

    @pytest.mark.asyncio
    async def test_handuo_query(self):
        """query() returns dict with answer, sources, confidence."""
        result = await self.agent.query("What is dissolution?")
        assert isinstance(result, dict)
        assert "answer" in result
        assert "sources" in result
        assert "confidence" in result
        assert isinstance(result["answer"], str)
        assert isinstance(result["sources"], list)
        assert isinstance(result["confidence"], (int, float))

    @pytest.mark.asyncio
    async def test_handuo_query_with_context(self):
        """query() with context dict should succeed."""
        context = {"tank_level": 3.5, "flow_rate": 0.02}
        result = await self.agent.query("dissolution process status", context=context)
        assert isinstance(result, dict)
        assert "answer" in result
        assert "sources" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_handuo_diagnose_anomaly(self):
        """diagnose_anomaly() returns causal reasoning dict."""
        anomaly_data = {"type": "pipe_leak", "location": "section_A3"}
        system_state = {"pressure": 0.25, "flow": 120.0}
        result = await self.agent.diagnose_anomaly(anomaly_data, system_state)
        assert isinstance(result, dict)
        assert "diagnosis" in result
        assert "possible_causes" in result
        assert "recommended_actions" in result
        assert "confidence" in result
        # Should match the pipe_leak fault mode from ontology
        assert result["matched_fault_mode"] == "pipe_leak"
        assert len(result["possible_causes"]) > 0

    @pytest.mark.asyncio
    async def test_handuo_generate_insight(self):
        """generate_insight() returns a string insight."""
        data = {"total_intake": 500.0, "reuse_rate": 0.65, "anomalies": []}
        result = await self.agent.generate_insight(data, report_type="daily")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "500.0" in result  # total_intake should appear

    @pytest.mark.asyncio
    async def test_handuo_no_llm_fallback(self):
        """Without LLM, query returns template response with mode='template'."""
        assert self.agent._llm is None
        result = await self.agent.query("Tell me about evaporation")
        assert result["mode"] == "template"
        assert result["confidence"] == 0.5
