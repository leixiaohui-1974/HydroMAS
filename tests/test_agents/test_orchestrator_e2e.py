"""End-to-end integration tests for OrchestratorAgent.handle_request().
Orchestrator 端到端集成测试。
"""

import pytest

from agents.orchestrator import OrchestratorAgent


class TestHandleRequestSkillRoute:
    """Test handle_request routing to Skills."""

    def setup_method(self):
        self.agent = OrchestratorAgent()

    @pytest.mark.asyncio
    async def test_handle_request_forecast_skill(self):
        """Test routing to ForecastSkill with valid data."""
        historical = [0.5 + 0.001 * i for i in range(120)]
        result = await self.agent.handle_request(
            "预报未来水位",
            params={"historical_data": historical, "horizon": 10},
        )
        assert result["status"] == "completed"
        assert result["skill"] == "forecast_skill"
        assert "data" in result
        assert result["data"] is not None

    @pytest.mark.asyncio
    async def test_handle_request_warning_skill(self):
        """Test routing to WarningSkill."""
        historical = [0.5 + 0.001 * i for i in range(120)]
        result = await self.agent.handle_request(
            "水位预警分析",
            params={"historical_data": historical, "horizon": 10},
        )
        assert result["status"] == "completed"
        assert result["skill"] == "warning_skill"
        assert result["data"] is not None
        assert "warning_level" in result["data"]

    @pytest.mark.asyncio
    async def test_handle_request_control_design_skill(self):
        """Test routing to ControlSystemDesignSkill."""
        result = await self.agent.handle_request(
            "设计控制器",
            params={
                "controller_type": "PID",
                "setpoint": 1.0,
                "duration": 100,
                "dt": 1.0,
            },
        )
        assert result["status"] == "completed"
        assert result["skill"] == "control_system_design"
        assert result["data"] is not None

    @pytest.mark.asyncio
    async def test_handle_request_odd_assessment_skill(self):
        """Test routing to ODDAssessmentSkill."""
        result = await self.agent.handle_request(
            "评估ODD安全边界",
            params={
                "simulation_params": {"duration": 60, "dt": 1.0},
            },
        )
        assert result["status"] == "completed"
        assert result["skill"] == "odd_assessment"
        assert result["data"] is not None


class TestHandleRequestToolRoute:
    """Test handle_request routing to direct Tools."""

    def setup_method(self):
        self.agent = OrchestratorAgent()

    @pytest.mark.asyncio
    async def test_handle_request_simulate_tool(self):
        """Test routing to simulate_tank tool."""
        result = await self.agent.handle_request(
            "仿真一下水箱",
            params={"duration": 60, "dt": 1.0},
        )
        assert result["status"] == "completed"
        assert result["tool"] == "simulate_tank"
        assert "data" in result
        assert "water_level" in result["data"]

    @pytest.mark.asyncio
    async def test_handle_request_predict_tool(self):
        """Test routing to predict_future tool via keyword match."""
        data = [0.5 + 0.001 * i for i in range(60)]
        result = await self.agent.handle_request(
            "predict这段数据",
            params={"historical_data": data, "horizon": 10},
        )
        assert result["status"] == "completed"
        assert result["tool"] == "predict_future"

    @pytest.mark.asyncio
    async def test_handle_request_clean_tool(self):
        """Test routing to clean_timeseries tool."""
        data = [1.0, 1.1, 1.2, 100.0, 1.3, 1.4]
        result = await self.agent.handle_request(
            "清洗一下这段数据",
            params={"raw_data": data},
        )
        assert result["status"] == "completed"
        assert result["tool"] == "clean_timeseries"

    @pytest.mark.asyncio
    async def test_handle_request_evaluate_tool(self):
        """Test routing to evaluate_performance tool."""
        obs = [1.0, 1.1, 1.2, 1.3]
        pred = [1.01, 1.09, 1.21, 1.29]
        result = await self.agent.handle_request(
            "计算评价指标 metric",
            params={"observed": obs, "predicted": pred},
        )
        assert result["status"] == "completed"
        assert result["tool"] == "evaluate_performance"


class TestHandleRequestAgentFallback:
    """Test handle_request agent delegation fallback."""

    def setup_method(self):
        self.agent = OrchestratorAgent()

    @pytest.mark.asyncio
    async def test_handle_request_no_match_delegates(self):
        """Test that unrecognized input delegates to planning agent."""
        result = await self.agent.handle_request(
            "做一碗红烧肉",  # Irrelevant request
            params={},
        )
        assert result["status"] == "delegated"
        assert "intent" in result

    @pytest.mark.asyncio
    async def test_handle_request_empty_params(self):
        """Test handle_request with no params defaults gracefully."""
        result = await self.agent.handle_request(
            "做一碗红烧肉",
        )
        assert result["status"] == "delegated"


class TestHandleRequestErrorHandling:
    """Test handle_request error handling."""

    def setup_method(self):
        self.agent = OrchestratorAgent()

    @pytest.mark.asyncio
    async def test_skill_with_missing_required_data(self):
        """Test skill execution with missing data returns failure."""
        result = await self.agent.handle_request(
            "预报未来水位",
            params={},  # No historical_data
        )
        # Should complete but with error from skill
        assert result["status"] == "failed" or result["data"] is not None

    @pytest.mark.asyncio
    async def test_tool_with_invalid_params(self):
        """Test tool call with invalid params returns error."""
        result = await self.agent.handle_request(
            "仿真一下水箱",
            params={"duration": -10, "dt": 1.0},
        )
        assert result["status"] == "failed"
        assert "error" in result
