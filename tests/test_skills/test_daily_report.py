"""Integration tests for DailyReportSkill (日报)."""

import pytest

from skills.daily_report import DailyReportSkill

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
            "q_in": 95, "q_out": 90, "q_loss": 2, "q_evap": 1,
        },
        {
            "node_id": "n3", "node_type": "reuse",
            "q_in": 40, "q_out": 38, "q_loss": 0.5, "q_evap": 0,
        },
    ]


def _edges_data():
    return [["n1", "n2"], ["n2", "n3"]]


def _tower_params():
    return {"water_flow_m3h": 500.0, "t_in": 42.0, "t_out": 32.0}


def _weather():
    return {"t_db": 30.0, "t_wb": 22.0, "humidity": 0.5, "wind_speed": 3.0}


def _calc_params():
    return {"slurry_flow": 50.0, "moisture": 0.45, "temp": 1050.0}


def _mud_params():
    return {"mud_mass": 500.0, "moisture_ratio": 0.55}


# ---------------------------------------------------------------------------
# Mock tool functions
# ---------------------------------------------------------------------------

def _mock_calc_full_plant_balance(**kwargs):
    return {
        "total_input": 100.0,
        "total_output": 90.0,
        "residual": 10.0,
        "total_intake": 100.0,
        "total_consumption": 85.0,
        "total_loss": 2.5,
        "total_evap": 1.0,
        "reuse_rate": 0.40,
        "balance_error": 1.5,
        "node_residuals": {"n1": 5.0, "n2": 3.0, "n3": 1.5},
    }


def _mock_detect_balance_anomaly(**kwargs):
    return {
        "anomalies": [
            {"node": "n1", "description": "Intake residual exceeds threshold"},
        ],
        "classification": {"leak": ["n1"]},
        "n_anomalies": 1,
    }


def _mock_evaluate_water_kpi(**kwargs):
    return {
        "reuse_rate": 0.40,
        "reuse_rate_target": 0.50,
        "leak_rate": 0.025,
        "water_per_ton_alumina": 8.5,
        "pump_efficiency": 0.82,
        "balance_error": 1.5,
        "kpi_score": 65.0,
    }


def _mock_predict_total_evap_loss(**kwargs):
    return {
        "total_evap_loss": 672.0,
        "total_daily_m3": 672.0,
        "total_hourly_m3": 28.0,
        "breakdown": {
            "cooling_tower": {"daily_m3": 360.0},
            "calcination": {"daily_m3": 192.0},
            "red_mud": {"daily_m3": 120.0},
        },
    }


def _build_skill():
    """Create a DailyReportSkill with all tools mocked."""
    skill = DailyReportSkill()
    skill.register_tool("calc_full_plant_balance", _mock_calc_full_plant_balance)
    skill.register_tool("detect_balance_anomaly", _mock_detect_balance_anomaly)
    skill.register_tool("evaluate_water_kpi", _mock_evaluate_water_kpi)
    skill.register_tool("predict_total_evap_loss", _mock_predict_total_evap_loss)
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDailyReport:
    @pytest.mark.asyncio
    async def test_daily_report_init(self):
        """DailyReportSkill can be instantiated and has an execute method."""
        skill = DailyReportSkill()
        assert hasattr(skill, "execute")
        assert callable(skill.execute)

    @pytest.mark.asyncio
    async def test_daily_report_execute(self):
        """Full execution with all params returns success and a Markdown report."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
            "tower_params": _tower_params(),
            "weather": _weather(),
            "calc_params": _calc_params(),
            "mud_params": _mud_params(),
            "date": "2026-02-27",
        })
        assert result.success
        assert "report_markdown" in result.data
        assert "2026-02-27" in result.data["report_markdown"]
        assert "# Daily Operation Report" in result.data["report_markdown"]

    @pytest.mark.asyncio
    async def test_daily_report_missing_nodes(self):
        """Missing nodes_data/edges_data returns error."""
        skill = _build_skill()
        result = await skill.run({})
        assert not result.success
        assert "nodes_data" in result.error or "edges_data" in result.error

    @pytest.mark.asyncio
    async def test_daily_report_steps(self):
        """Verify steps_completed for a complete run."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
        })
        assert result.success
        assert result.steps_completed == [
            "water_balance",
            "anomaly_detection",
            "kpi_evaluation",
            "evaporation_estimation",
            "report_generation",
        ]

    @pytest.mark.asyncio
    async def test_daily_report_markdown_sections(self):
        """Report Markdown contains the expected sections."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
            "date": "2026-02-27",
        })
        assert result.success
        report = result.data["report_markdown"]
        assert "Water Balance" in report
        assert "Anomaly Detection" in report
        assert "KPI Evaluation" in report or "KPI" in report
        assert "Evaporation" in report

    @pytest.mark.asyncio
    async def test_daily_report_result_keys(self):
        """Result data contains all expected top-level keys."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
        })
        assert result.success
        expected_keys = {"report_markdown", "date", "balance", "anomalies", "kpi", "evaporation"}
        assert expected_keys == set(result.data.keys())

    @pytest.mark.asyncio
    async def test_daily_report_default_date(self):
        """When no date is provided, today's date is used automatically."""
        skill = _build_skill()
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
        })
        assert result.success
        # date should be a string in YYYY-MM-DD format
        date_str = result.data["date"]
        assert len(date_str) == 10
        assert date_str[4] == "-"
        assert date_str[7] == "-"

    @pytest.mark.asyncio
    async def test_daily_report_no_anomalies(self):
        """Report shows 'No anomalies' when none are detected."""
        def mock_no_anomalies(**kwargs):
            return {"anomalies": [], "classification": {}, "n_anomalies": 0}

        skill = _build_skill()
        skill.register_tool("detect_balance_anomaly", mock_no_anomalies)
        result = await skill.run({
            "nodes_data": _nodes_data(),
            "edges_data": _edges_data(),
        })
        assert result.success
        report = result.data["report_markdown"]
        assert "No anomalies detected" in report
