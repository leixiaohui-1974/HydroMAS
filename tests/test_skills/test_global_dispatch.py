"""Integration tests for GlobalDispatchSkill (全局调度)."""

import pytest

from skills.global_dispatch import GlobalDispatchSkill

# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

def _historical_demand():
    return [100.0, 105.0, 110.0, 108.0, 112.0, 115.0, 120.0, 118.0, 116.0, 114.0]


def _weather_forecast():
    return [
        {"t_db": 30.0, "t_wb": 22.0, "humidity": 0.5, "wind_speed": 3.0},
        {"t_db": 32.0, "t_wb": 23.0, "humidity": 0.45, "wind_speed": 2.5},
        {"t_db": 28.0, "t_wb": 21.0, "humidity": 0.55, "wind_speed": 4.0},
    ]


def _supply_config():
    return {
        "river_intake": {"capacity": 500.0, "cost_per_m3": 2.0},
        "well_field": {"capacity": 200.0, "cost_per_m3": 3.5},
    }


def _current_state():
    return {
        "reservoir_level": 0.75,
        "total_demand": 350.0,
    }


# ---------------------------------------------------------------------------
# Mock tool functions
# ---------------------------------------------------------------------------

def _mock_predict_demand(historical_data, **kwargs):
    return {
        "predictions": [120.0, 122.0, 125.0],
        "model_type": "linear",
    }


def _mock_predict_evaporation_hybrid(historical_evap, weather_forecast, **kwargs):
    return {
        "predictions": [15.0, 16.0, 14.0],
        "method": "data_driven",
        "horizon": 3,
    }


def _mock_optimize_global_dispatch(demand_forecast, supply_config, **kwargs):
    total_supply = sum(demand_forecast.values()) if isinstance(demand_forecast, dict) else 0
    return {
        "total_supply": total_supply,
        "allocation": {"river_intake": 300.0, "well_field": 112.0},
        "deficit": 0.0,
        "feasible": True,
        "method": "lp",
    }


def _mock_check_alumina_odd(current_state, **kwargs):
    return {
        "zone": "normal",
        "violations": [],
        "n_checked": 5,
        "n_violations": 0,
    }


def _build_skill():
    """Create a GlobalDispatchSkill with all tools mocked."""
    skill = GlobalDispatchSkill()
    skill.register_tool("predict_demand", _mock_predict_demand)
    skill.register_tool("predict_evaporation_hybrid", _mock_predict_evaporation_hybrid)
    skill.register_tool("optimize_global_dispatch", _mock_optimize_global_dispatch)
    skill.register_tool("check_alumina_odd", _mock_check_alumina_odd)
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGlobalDispatch:
    @pytest.mark.asyncio
    async def test_global_dispatch_init(self):
        """GlobalDispatchSkill can be instantiated and has an execute method."""
        skill = GlobalDispatchSkill()
        assert hasattr(skill, "execute")
        assert callable(skill.execute)

    @pytest.mark.asyncio
    async def test_global_dispatch_execute(self):
        """Full execution with all params returns success and expected data keys."""
        skill = _build_skill()
        result = await skill.run({
            "historical_demand": _historical_demand(),
            "weather_forecast": _weather_forecast(),
            "supply_config": _supply_config(),
            "current_state": _current_state(),
        })
        assert result.success
        assert "demand_forecast" in result.data
        assert "evaporation_forecast" in result.data
        assert "dispatch_plan" in result.data
        assert "odd_check" in result.data
        assert "summary" in result.data

    @pytest.mark.asyncio
    async def test_global_dispatch_missing_demand(self):
        """Missing historical_demand returns error."""
        skill = _build_skill()
        result = await skill.run({})
        assert not result.success
        assert "historical_demand" in result.error

    @pytest.mark.asyncio
    async def test_global_dispatch_steps_full(self):
        """Verify all steps completed when weather_forecast is provided."""
        skill = _build_skill()
        result = await skill.run({
            "historical_demand": _historical_demand(),
            "weather_forecast": _weather_forecast(),
            "supply_config": _supply_config(),
            "current_state": _current_state(),
        })
        assert result.success
        assert result.steps_completed == [
            "demand_prediction",
            "evaporation_prediction",
            "dispatch_optimization",
            "odd_safety_check",
        ]

    @pytest.mark.asyncio
    async def test_global_dispatch_no_weather(self):
        """Without weather_forecast, evaporation prediction step is skipped."""
        skill = _build_skill()
        result = await skill.run({
            "historical_demand": _historical_demand(),
            "supply_config": _supply_config(),
        })
        assert result.success
        assert "evaporation_prediction" not in result.steps_completed
        assert "demand_prediction" in result.steps_completed
        assert "dispatch_optimization" in result.steps_completed
        assert "odd_safety_check" in result.steps_completed

    @pytest.mark.asyncio
    async def test_global_dispatch_summary_structure(self):
        """Summary dict has expected keys and reasonable values."""
        skill = _build_skill()
        result = await skill.run({
            "historical_demand": _historical_demand(),
            "weather_forecast": _weather_forecast(),
            "supply_config": _supply_config(),
            "current_state": _current_state(),
        })
        assert result.success
        summary = result.data["summary"]
        assert "total_predicted_demand" in summary
        assert "total_predicted_evap" in summary
        assert "total_planned_supply" in summary
        assert "odd_zone" in summary
        assert "is_safe" in summary
        assert "message" in summary
        assert summary["is_safe"] is True
        assert summary["odd_zone"] == "normal"

    @pytest.mark.asyncio
    async def test_global_dispatch_odd_extended(self):
        """When ODD check returns extended zone, summary reflects it."""
        def mock_odd_extended(current_state, **kwargs):
            return {
                "zone": "extended",
                "violations": [{"dimension": "reservoir_level", "value": 0.15}],
                "n_checked": 5,
                "n_violations": 1,
            }

        skill = _build_skill()
        skill.register_tool("check_alumina_odd", mock_odd_extended)
        result = await skill.run({
            "historical_demand": _historical_demand(),
            "supply_config": _supply_config(),
        })
        assert result.success
        assert result.data["summary"]["odd_zone"] == "extended"
        assert result.data["summary"]["is_safe"] is True  # extended is still safe
