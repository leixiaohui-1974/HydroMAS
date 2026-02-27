"""Integration tests for MCP evaporation server."""

import pytest
from mcp_servers.evaporation_server import (
    predict_evaporation,
    predict_calcination_evap,
    predict_red_mud_water,
    predict_total_evap_loss,
)


class TestPredictEvaporation:
    def test_predict_evaporation_normal(self):
        """Valid tower params and weather returns evaporation result."""
        tower_params = {
            "water_flow_m3h": 500.0,
            "t_in": 42.0,
            "t_out": 32.0,
            "n_cells": 4,
            "fan_power_kw": 55.0,
        }
        weather = {
            "t_db": 35.0,
            "t_wb": 28.0,
            "humidity": 0.6,
            "wind_speed": 2.0,
        }
        result = predict_evaporation(tower_params=tower_params, weather=weather)
        assert isinstance(result, dict)
        assert "evap_rate_m3h" in result
        assert "evap_daily_m3" in result
        assert "evap_ratio" in result
        assert result["evap_rate_m3h"] > 0
        assert result["evap_daily_m3"] == pytest.approx(result["evap_rate_m3h"] * 24.0)

    def test_predict_evaporation_bad_params(self):
        """Invalid tower params (non-positive water flow) raises ValueError."""
        tower_params = {
            "water_flow_m3h": -100.0,
            "t_in": 42.0,
            "t_out": 32.0,
        }
        weather = {
            "t_db": 35.0,
            "t_wb": 28.0,
            "humidity": 0.6,
            "wind_speed": 2.0,
        }
        with pytest.raises(ValueError):
            predict_evaporation(tower_params=tower_params, weather=weather)


class TestPredictCalcinationEvap:
    def test_predict_calcination_evap_normal(self):
        """Valid calcination parameters return evaporation result."""
        result = predict_calcination_evap(
            slurry_flow=50.0,
            moisture=0.45,
            temp=1050.0,
        )
        assert isinstance(result, dict)
        assert "evap_rate_m3h" in result
        assert "evap_daily_m3" in result
        assert "energy_consumption_kwh" in result
        assert result["evap_rate_m3h"] > 0
        assert result["evap_daily_m3"] == pytest.approx(result["evap_rate_m3h"] * 24.0)
        assert result["energy_consumption_kwh"] > 0


class TestPredictRedMudWater:
    def test_predict_red_mud_water_normal(self):
        """Valid red mud params return water carry-out volumes."""
        result = predict_red_mud_water(
            mud_mass=500.0,
            moisture_ratio=0.55,
        )
        assert isinstance(result, dict)
        assert "water_carry_m3d" in result
        assert "water_carry_m3h" in result
        assert result["water_carry_m3d"] > 0
        # Q = M * w / (1-w) = 500 * 0.55 / 0.45 ≈ 611.11
        assert result["water_carry_m3d"] == pytest.approx(
            500.0 * 0.55 / 0.45, rel=1e-3
        )
        assert result["water_carry_m3h"] == pytest.approx(
            result["water_carry_m3d"] / 24.0
        )


class TestPredictTotalEvapLoss:
    def test_predict_total_evap_loss(self):
        """All three sources combined return a total daily loss."""
        tower_params = {
            "water_flow_m3h": 500.0,
            "t_in": 42.0,
            "t_out": 32.0,
            "n_cells": 4,
            "fan_power_kw": 55.0,
        }
        weather = {
            "t_db": 35.0,
            "t_wb": 28.0,
            "humidity": 0.6,
            "wind_speed": 2.0,
        }
        calc_params = {
            "slurry_flow": 50.0,
            "moisture": 0.45,
            "temp": 1050.0,
        }
        mud_params = {
            "mud_mass": 500.0,
            "moisture_ratio": 0.55,
        }
        result = predict_total_evap_loss(
            tower_params=tower_params,
            weather=weather,
            calc_params=calc_params,
            mud_params=mud_params,
        )
        assert isinstance(result, dict)
        assert "total_daily_m3" in result
        assert "total_hourly_m3" in result
        assert result["total_daily_m3"] > 0
        assert result["total_hourly_m3"] > 0
        # Total should be sum of all three breakdown components
        breakdown = result["breakdown"]
        expected_daily = (
            breakdown["cooling_tower"]["daily_m3"]
            + breakdown["calcination"]["daily_m3"]
            + breakdown["red_mud"]["daily_m3"]
        )
        assert result["total_daily_m3"] == pytest.approx(expected_daily)

    def test_predict_total_evap_loss_keys(self):
        """Verify all expected keys in result dict."""
        tower_params = {
            "water_flow_m3h": 300.0,
            "t_in": 40.0,
            "t_out": 30.0,
        }
        weather = {
            "t_db": 30.0,
            "t_wb": 25.0,
            "humidity": 0.5,
            "wind_speed": 1.5,
        }
        calc_params = {
            "slurry_flow": 30.0,
            "moisture": 0.40,
            "temp": 900.0,
        }
        mud_params = {
            "mud_mass": 300.0,
            "moisture_ratio": 0.50,
        }
        result = predict_total_evap_loss(
            tower_params=tower_params,
            weather=weather,
            calc_params=calc_params,
            mud_params=mud_params,
        )
        assert "total_daily_m3" in result
        assert "total_hourly_m3" in result
        assert "breakdown" in result
        assert "details" in result
        # Check breakdown sub-keys
        breakdown = result["breakdown"]
        for source in ("cooling_tower", "calcination", "red_mud"):
            assert source in breakdown
            assert "daily_m3" in breakdown[source]
            assert "hourly_m3" in breakdown[source]
        # Check details sub-keys
        details = result["details"]
        for source in ("cooling_tower", "calcination", "red_mud"):
            assert source in details
