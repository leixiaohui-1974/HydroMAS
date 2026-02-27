"""Tests for AnalysisAgent and ReportAgent."""

import pytest

from agents.analysis_agent import AnalysisAgent
from agents.report_agent import ReportAgent


class TestAnalysisAgent:
    @pytest.mark.asyncio
    async def test_compare_schemes(self):
        agent = AnalysisAgent()
        schemes = [
            {"duration": 50, "q_in_profile": [[0, 0.01]], "initial_h": 0.5},
            {"duration": 50, "q_in_profile": [[0, 0.03]], "initial_h": 0.5},
        ]
        result = await agent.compare_schemes(schemes)
        assert result["n_schemes"] == 2
        assert len(result["results"]) == 2
        assert len(result["ranking"]) == 2

    @pytest.mark.asyncio
    async def test_visualization_code(self):
        agent = AnalysisAgent()
        data = {"time": [0, 1, 2], "water_level": [0.5, 0.6, 0.7]}
        code = await agent.generate_visualization_code(data, plot_type="time_series")
        assert "matplotlib" in code
        assert "water_level" in code


class TestReportAgent:
    def test_control_report(self):
        agent = ReportAgent()
        results = {
            "performance_metrics": {"RMSE": 0.05, "MAE": 0.03},
            "control_simulation": {
                "setpoint": 1.0,
                "water_level": [0.5, 0.8, 0.95, 1.0],
                "metadata": {"solver": "Euler", "steps": 100, "dt": 1.0},
            },
            "controller_type": "PID",
        }
        report = agent.generate_control_report(results)
        assert "PID" in report
        assert "RMSE" in report

    def test_odd_report(self):
        agent = ReportAgent()
        results = {
            "current_odd_status": {"zone": "normal", "n_violations": 0},
            "overall_assessment": {
                "scenarios_tested": 3,
                "scenarios_with_violations": 0,
                "safety_rating": "safe",
            },
        }
        report = agent.generate_odd_report(results)
        assert "normal" in report
        assert "safe" in report

    def test_lifecycle_report(self):
        agent = ReportAgent()
        results = {
            "summary": {
                "tank_area": 1.5,
                "controller": "PID",
                "setpoint": 1.0,
                "odd_zone": "normal",
            },
            "evaluation": {"RMSE": 0.05, "NSE": 0.92},
        }
        report = agent.generate_lifecycle_report(results)
        assert "PID" in report
        assert "1.5" in report
