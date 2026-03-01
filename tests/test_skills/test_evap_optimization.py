"""Integration tests for EvapOptimizationSkill (蒸发优化)."""

import pytest

from skills.evap_optimization import EvapOptimizationSkill

# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

def _tower_params():
    return {
        "water_flow_m3h": 500.0,
        "t_in": 42.0,
        "t_out": 32.0,
        "n_cells": 4,
        "fan_power_kw": 55.0,
    }


def _weather():
    return {
        "t_db": 30.0,
        "t_wb": 22.0,
        "humidity": 0.5,
        "wind_speed": 3.0,
        "temperature": 30.0,
    }


def _calc_params():
    return {"slurry_flow": 50.0, "moisture": 0.45, "temp": 1050.0}


def _mud_params():
    return {"mud_mass": 500.0, "moisture_ratio": 0.55}


# ---------------------------------------------------------------------------
# Mock tool functions
# ---------------------------------------------------------------------------

def _mock_predict_evaporation(tower_params, weather):
    return {
        "evap_rate_m3h": 15.0,
        "evap_daily_m3": 360.0,
        "evap_ratio": 0.03,
    }


def _mock_predict_calcination_evap(slurry_flow, moisture, temp):
    return {
        "evap_rate_m3h": 8.0,
        "evap_daily_m3": 192.0,
    }


def _mock_predict_red_mud_water(mud_mass, moisture_ratio):
    return {
        "water_loss": 120.0,
        "water_carry_m3d": 120.0,
        "water_carry_m3h": 5.0,
    }


def _mock_predict_total_evap_loss(tower_params, weather, calc_params, mud_params):
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
    """Create an EvapOptimizationSkill with all tools mocked."""
    skill = EvapOptimizationSkill()
    skill.register_tool("predict_evaporation", _mock_predict_evaporation)
    skill.register_tool("predict_calcination_evap", _mock_predict_calcination_evap)
    skill.register_tool("predict_red_mud_water", _mock_predict_red_mud_water)
    skill.register_tool("predict_total_evap_loss", _mock_predict_total_evap_loss)
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEvapOptimization:
    @pytest.mark.asyncio
    async def test_evap_optimization_init(self):
        """EvapOptimizationSkill can be instantiated and has an execute method."""
        skill = EvapOptimizationSkill()
        assert hasattr(skill, "execute")
        assert callable(skill.execute)

    @pytest.mark.asyncio
    async def test_evap_optimization_execute(self):
        """Full execution with tower_params and weather returns success."""
        skill = _build_skill()
        result = await skill.run({
            "tower_params": _tower_params(),
            "weather": _weather(),
            "calc_params": _calc_params(),
            "mud_params": _mud_params(),
        })
        assert result.success
        assert "tower_evaporation" in result.data
        assert "calcination_evaporation" in result.data
        assert "red_mud_water" in result.data
        assert "total_evap_loss" in result.data
        assert "suggestions" in result.data

    @pytest.mark.asyncio
    async def test_evap_optimization_missing_params(self):
        """No tower/calc/mud params returns error."""
        skill = _build_skill()
        result = await skill.run({})
        assert not result.success
        assert (
            "tower_params" in result.error
            or "calc_params" in result.error
            or "mud_params" in result.error
        )

    @pytest.mark.asyncio
    async def test_evap_optimization_steps(self):
        """Verify steps_completed for full execution."""
        skill = _build_skill()
        result = await skill.run({
            "tower_params": _tower_params(),
            "weather": _weather(),
            "calc_params": _calc_params(),
            "mud_params": _mud_params(),
        })
        assert result.success
        assert "tower_evaporation" in result.steps_completed
        assert "calcination_evaporation" in result.steps_completed
        assert "red_mud_water" in result.steps_completed
        assert "total_evap_loss" in result.steps_completed
        assert "optimization_suggestions" in result.steps_completed

    @pytest.mark.asyncio
    async def test_evap_optimization_result_keys(self):
        """Result data keys match expected structure."""
        skill = _build_skill()
        result = await skill.run({
            "tower_params": _tower_params(),
            "weather": _weather(),
        })
        assert result.success
        expected_keys = {
            "tower_evaporation",
            "calcination_evaporation",
            "red_mud_water",
            "total_evap_loss",
            "suggestions",
        }
        assert expected_keys == set(result.data.keys())

    @pytest.mark.asyncio
    async def test_evap_optimization_tower_only(self):
        """Providing only tower_params skips calcination and red mud steps."""
        skill = _build_skill()
        result = await skill.run({
            "tower_params": _tower_params(),
            "weather": _weather(),
        })
        assert result.success
        assert "tower_evaporation" in result.steps_completed
        assert "calcination_evaporation" not in result.steps_completed
        assert "red_mud_water" not in result.steps_completed

    @pytest.mark.asyncio
    async def test_evap_optimization_suggestions_generated(self):
        """Suggestions list is non-empty for typical inputs."""
        skill = _build_skill()
        result = await skill.run({
            "tower_params": _tower_params(),
            "weather": _weather(),
            "mud_params": _mud_params(),
        })
        assert result.success
        suggestions = result.data["suggestions"]
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        for s in suggestions:
            assert "target" in s
            assert "priority" in s
            assert "action" in s
