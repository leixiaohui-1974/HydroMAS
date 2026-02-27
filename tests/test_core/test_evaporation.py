"""Tests for core.evaporation module.
core.evaporation 模块测试。
"""

import pytest

from core.evaporation.calcination_model import CalcinationParams, calc_calcination_evap
from core.evaporation.merkel_model import (
    CoolingTowerParams,
    calc_evap_rate,
    calc_evaporation_merkel,
)
from core.evaporation.red_mud_model import RedMudParams, calc_red_mud_water


class TestCoolingTowerParams:
    def test_cooling_tower_params_defaults(self):
        """Default dataclass values match expected constants."""
        p = CoolingTowerParams()
        assert p.water_flow_m3h == 500.0
        assert p.t_in == 42.0
        assert p.t_out == 32.0
        assert p.n_cells == 4
        assert p.fan_power_kw == 55.0

    def test_cooling_tower_params_validate_good(self):
        """Valid parameters pass validation without error."""
        p = CoolingTowerParams(
            water_flow_m3h=600.0,
            t_in=45.0,
            t_out=33.0,
            n_cells=6,
            fan_power_kw=75.0,
        )
        p.validate()  # should not raise

    def test_cooling_tower_params_validate_bad_temp(self):
        """t_in <= t_out raises ValueError."""
        p = CoolingTowerParams(t_in=30.0, t_out=35.0)
        with pytest.raises(ValueError, match="Inlet temperature"):
            p.validate()

    def test_cooling_tower_params_validate_bad_temp_equal(self):
        """t_in == t_out also raises ValueError."""
        p = CoolingTowerParams(t_in=35.0, t_out=35.0)
        with pytest.raises(ValueError, match="Inlet temperature"):
            p.validate()

    def test_cooling_tower_params_validate_bad_flow(self):
        """water_flow <= 0 raises ValueError."""
        p = CoolingTowerParams(water_flow_m3h=0.0)
        with pytest.raises(ValueError, match="Water flow must be positive"):
            p.validate()

    def test_cooling_tower_params_validate_bad_flow_negative(self):
        """Negative water_flow raises ValueError."""
        p = CoolingTowerParams(water_flow_m3h=-10.0)
        with pytest.raises(ValueError, match="Water flow must be positive"):
            p.validate()

    def test_cooling_tower_params_validate_bad_cells(self):
        """Zero cells raises ValueError."""
        p = CoolingTowerParams(n_cells=0)
        with pytest.raises(ValueError, match="Number of cells must be positive"):
            p.validate()

    def test_cooling_tower_params_validate_bad_fan_power(self):
        """Negative fan power raises ValueError."""
        p = CoolingTowerParams(fan_power_kw=-5.0)
        with pytest.raises(ValueError, match="Fan power must be non-negative"):
            p.validate()


class TestCalcEvaporationMerkel:
    def test_calc_evaporation_merkel_normal(self):
        """Normal weather conditions produce expected result keys and positive values."""
        params = CoolingTowerParams()
        weather = {"t_db": 35.0, "t_wb": 28.0, "humidity": 0.6, "wind_speed": 2.0}
        result = calc_evaporation_merkel(params, weather)

        # Check top-level keys
        assert "evap_rate_m3h" in result
        assert "evap_daily_m3" in result
        assert "evap_ratio" in result
        assert "details" in result

        # Positive evaporation
        assert result["evap_rate_m3h"] > 0
        assert result["evap_daily_m3"] > 0
        assert 0 < result["evap_ratio"] < 1

        # Daily = hourly * 24
        assert abs(result["evap_daily_m3"] - result["evap_rate_m3h"] * 24.0) < 1e-9

        # Details sub-keys
        details = result["details"]
        assert "latent_heat" in details
        assert "k_evap" in details
        assert "q_heat_kjh" in details
        assert "evap_mass_kgh" in details
        assert "delta_t" in details
        assert "t_avg" in details
        assert "weather" in details
        assert "n_cells" in details
        assert "fan_power_kw" in details

    def test_calc_evaporation_merkel_extreme_weather(self):
        """High temperature, low humidity produces valid but larger evaporation."""
        params = CoolingTowerParams(water_flow_m3h=1000.0, t_in=50.0, t_out=35.0)
        weather = {"t_db": 45.0, "t_wb": 38.0, "humidity": 0.1, "wind_speed": 5.0}
        result = calc_evaporation_merkel(params, weather)

        assert result["evap_rate_m3h"] > 0
        assert result["evap_daily_m3"] > 0
        # With higher flow and larger delta_t, evap should be larger
        assert result["evap_rate_m3h"] > 5.0  # rough sanity check

    def test_calc_evaporation_merkel_weather_defaults(self):
        """Missing weather keys should use defaults without error."""
        params = CoolingTowerParams()
        weather = {}  # all defaults
        result = calc_evaporation_merkel(params, weather)
        assert result["evap_rate_m3h"] > 0

    def test_calc_evaporation_merkel_k_evap_clamped(self):
        """K_evap should always be within [0.85, 1.15]."""
        params = CoolingTowerParams()
        weather = {"t_db": 35.0, "t_wb": 28.0, "humidity": 0.6, "wind_speed": 2.0}
        result = calc_evaporation_merkel(params, weather)
        k = result["details"]["k_evap"]
        assert 0.85 <= k <= 1.15

    def test_calc_evaporation_merkel_delta_t_correct(self):
        """Verify delta_t in details matches t_in - t_out."""
        params = CoolingTowerParams(t_in=50.0, t_out=38.0)
        weather = {"t_db": 35.0, "t_wb": 28.0}
        result = calc_evaporation_merkel(params, weather)
        assert abs(result["details"]["delta_t"] - 12.0) < 1e-9

    def test_calc_evaporation_merkel_t_avg_correct(self):
        """Verify t_avg in details matches (t_in + t_out) / 2."""
        params = CoolingTowerParams(t_in=50.0, t_out=30.0)
        weather = {}
        result = calc_evaporation_merkel(params, weather)
        assert abs(result["details"]["t_avg"] - 40.0) < 1e-9


class TestCalcEvapRate:
    def test_calc_evap_rate_basic(self):
        """Simplified calculation returns positive float."""
        rate = calc_evap_rate(t_in=42.0, t_out=32.0, water_flow=500.0, t_wb=28.0)
        assert isinstance(rate, float)
        assert rate > 0

    def test_calc_evap_rate_bad_temp(self):
        """t_in <= t_out should raise ValueError."""
        with pytest.raises(ValueError, match="Inlet temperature"):
            calc_evap_rate(t_in=30.0, t_out=35.0, water_flow=500.0, t_wb=28.0)

    def test_calc_evap_rate_bad_flow(self):
        """water_flow <= 0 should raise ValueError."""
        with pytest.raises(ValueError, match="Water flow must be positive"):
            calc_evap_rate(t_in=42.0, t_out=32.0, water_flow=0.0, t_wb=28.0)

    def test_calc_evap_rate_consistency(self):
        """Simplified rate should be close to the detailed Merkel result."""
        params = CoolingTowerParams(water_flow_m3h=500.0, t_in=42.0, t_out=32.0)
        weather = {"t_wb": 28.0, "wind_speed": 2.0}
        detailed = calc_evaporation_merkel(params, weather)
        simple = calc_evap_rate(t_in=42.0, t_out=32.0, water_flow=500.0, t_wb=28.0)
        # Both use the same physics; should be very close
        assert abs(detailed["evap_rate_m3h"] - simple) < 1e-6


class TestCalcinationParams:
    def test_calcination_params_validate_good(self):
        """Valid parameters pass validation without error."""
        p = CalcinationParams(slurry_flow_m3h=60.0, moisture_content=0.5, calcination_temp=1000.0)
        p.validate()  # should not raise

    def test_calcination_params_validate_bad_flow(self):
        """Zero slurry flow raises ValueError."""
        p = CalcinationParams(slurry_flow_m3h=0.0)
        with pytest.raises(ValueError, match="Slurry flow must be positive"):
            p.validate()

    def test_calcination_params_validate_bad_moisture_low(self):
        """Moisture content at 0.0 boundary raises ValueError."""
        p = CalcinationParams(moisture_content=0.0)
        with pytest.raises(ValueError, match="Moisture content must be in"):
            p.validate()

    def test_calcination_params_validate_bad_moisture_high(self):
        """Moisture content at 1.0 boundary raises ValueError."""
        p = CalcinationParams(moisture_content=1.0)
        with pytest.raises(ValueError, match="Moisture content must be in"):
            p.validate()

    def test_calcination_params_validate_bad_temp(self):
        """Zero calcination temperature raises ValueError."""
        p = CalcinationParams(calcination_temp=0.0)
        with pytest.raises(ValueError, match="Calcination temperature must be positive"):
            p.validate()

    def test_calcination_params_validate_negative_flow(self):
        """Negative slurry flow raises ValueError."""
        p = CalcinationParams(slurry_flow_m3h=-5.0)
        with pytest.raises(ValueError, match="Slurry flow must be positive"):
            p.validate()


class TestCalcCalcinationEvap:
    def test_calc_calcination_evap_normal(self):
        """Normal operation produces expected keys and positive values."""
        params = CalcinationParams()
        result = calc_calcination_evap(params)

        assert "evap_rate_m3h" in result
        assert "evap_daily_m3" in result
        assert "energy_consumption_kwh" in result
        assert "details" in result

        assert result["evap_rate_m3h"] > 0
        assert result["evap_daily_m3"] > 0
        assert result["energy_consumption_kwh"] > 0

        # Daily = hourly * 24
        assert abs(result["evap_daily_m3"] - result["evap_rate_m3h"] * 24.0) < 1e-9

        # Efficiency should be close to 1.0 at default 1050C
        assert result["details"]["efficiency"] > 0.99

    def test_calc_calcination_evap_low_temp(self):
        """Lower temperature gives lower efficiency."""
        params_low = CalcinationParams(calcination_temp=200.0)
        params_high = CalcinationParams(calcination_temp=1050.0)
        result_low = calc_calcination_evap(params_low)
        result_high = calc_calcination_evap(params_high)
        assert result_low["details"]["efficiency"] < result_high["details"]["efficiency"]

    def test_calc_calcination_evap_energy_positive(self):
        """Energy consumption should be positive and proportional to evap rate."""
        params_small = CalcinationParams(slurry_flow_m3h=10.0)
        params_large = CalcinationParams(slurry_flow_m3h=100.0)
        result_small = calc_calcination_evap(params_small)
        result_large = calc_calcination_evap(params_large)
        assert result_large["energy_consumption_kwh"] > result_small["energy_consumption_kwh"]


class TestRedMudParams:
    def test_red_mud_params_validate_good(self):
        """Valid parameters pass validation without error."""
        p = RedMudParams(mud_dry_mass_td=400.0, moisture_ratio=0.5)
        p.validate()  # should not raise

    def test_red_mud_params_validate_bad_mass(self):
        """Zero dry mud mass raises ValueError."""
        p = RedMudParams(mud_dry_mass_td=0.0)
        with pytest.raises(ValueError, match="Dry mud mass must be positive"):
            p.validate()

    def test_red_mud_params_validate_bad_moisture_low(self):
        """Moisture ratio at 0.0 boundary raises ValueError."""
        p = RedMudParams(moisture_ratio=0.0)
        with pytest.raises(ValueError, match="Moisture ratio must be in"):
            p.validate()

    def test_red_mud_params_validate_bad_moisture_high(self):
        """Moisture ratio at 1.0 boundary raises ValueError."""
        p = RedMudParams(moisture_ratio=1.0)
        with pytest.raises(ValueError, match="Moisture ratio must be in"):
            p.validate()

    def test_red_mud_params_validate_negative_mass(self):
        """Negative dry mud mass raises ValueError."""
        p = RedMudParams(mud_dry_mass_td=-100.0)
        with pytest.raises(ValueError, match="Dry mud mass must be positive"):
            p.validate()


class TestCalcRedMudWater:
    def test_calc_red_mud_water_normal(self):
        """Normal operation produces expected keys and positive values."""
        params = RedMudParams()
        result = calc_red_mud_water(params)

        assert "water_carry_m3d" in result
        assert "water_carry_m3h" in result
        assert "details" in result

        assert result["water_carry_m3d"] > 0
        assert result["water_carry_m3h"] > 0

        # Hourly = daily / 24
        assert abs(result["water_carry_m3h"] - result["water_carry_m3d"] / 24.0) < 1e-9

        # Verify formula: Q = M * w / (1 - w)
        expected = 500.0 * 0.55 / (1.0 - 0.55)
        assert abs(result["water_carry_m3d"] - expected) < 1e-9

    def test_calc_red_mud_water_zero(self):
        """Edge case: very small values produce very small but positive results."""
        params = RedMudParams(mud_dry_mass_td=0.001, moisture_ratio=0.01)
        result = calc_red_mud_water(params)

        assert result["water_carry_m3d"] > 0
        assert result["water_carry_m3d"] < 0.001  # very small
        assert result["water_carry_m3h"] > 0

    def test_calc_red_mud_water_high_moisture(self):
        """High moisture ratio produces larger water carry-out."""
        params_low = RedMudParams(moisture_ratio=0.3)
        params_high = RedMudParams(moisture_ratio=0.7)
        result_low = calc_red_mud_water(params_low)
        result_high = calc_red_mud_water(params_high)
        assert result_high["water_carry_m3d"] > result_low["water_carry_m3d"]

    def test_calc_red_mud_water_details_keys(self):
        """Details dict contains expected keys with correct values."""
        params = RedMudParams(mud_dry_mass_td=300.0, moisture_ratio=0.4)
        result = calc_red_mud_water(params)
        details = result["details"]
        assert details["mud_dry_mass_td"] == 300.0
        assert details["moisture_ratio"] == 0.4
        assert details["water_carry_td"] > 0
