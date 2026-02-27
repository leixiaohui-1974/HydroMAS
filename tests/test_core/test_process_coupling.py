"""Tests for core.process_coupling module.
core.process_coupling 模块测试。
"""

import pytest

from core.process_coupling.alumina_process import (
    ProcessState,
    calc_decomposition_water,
    calc_dissolution_water,
    calc_evaporation_makeup,
    calc_total_process_demand,
)


class TestProcessState:
    def test_process_state_defaults(self):
        """Default dataclass values are all 0.0."""
        s = ProcessState()
        assert s.ore_feed_td == 0.0
        assert s.alkali_concentration == 0.0
        assert s.dissolution_temp == 0.0
        assert s.decomposition_temp == 0.0
        assert s.evaporation_ratio == 0.0

    def test_process_state_validate_good(self):
        """Valid positive parameters pass validation without error."""
        s = ProcessState(
            ore_feed_td=1000.0,
            alkali_concentration=220.0,
            dissolution_temp=250.0,
            decomposition_temp=60.0,
            evaporation_ratio=0.15,
        )
        s.validate()  # should not raise

    def test_process_state_validate_good_zero(self):
        """All-zero state is valid (>=0 checks)."""
        s = ProcessState()
        s.validate()  # should not raise

    def test_process_state_validate_bad(self):
        """Negative ore_feed raises ValueError."""
        s = ProcessState(ore_feed_td=-1.0)
        with pytest.raises(ValueError, match="Ore feed rate must be >= 0"):
            s.validate()

    def test_process_state_validate_bad_alkali(self):
        """Negative alkali concentration raises ValueError."""
        s = ProcessState(alkali_concentration=-5.0)
        with pytest.raises(ValueError, match="Alkali concentration must be >= 0"):
            s.validate()

    def test_process_state_validate_bad_dissolution_temp(self):
        """Negative dissolution temperature raises ValueError."""
        s = ProcessState(dissolution_temp=-10.0)
        with pytest.raises(ValueError, match="Dissolution temperature must be >= 0"):
            s.validate()

    def test_process_state_validate_bad_decomposition_temp(self):
        """Negative decomposition temperature raises ValueError."""
        s = ProcessState(decomposition_temp=-1.0)
        with pytest.raises(ValueError, match="Decomposition temperature must be >= 0"):
            s.validate()

    def test_process_state_validate_bad_evaporation_ratio(self):
        """Negative evaporation ratio raises ValueError."""
        s = ProcessState(evaporation_ratio=-0.5)
        with pytest.raises(ValueError, match="Evaporation ratio must be >= 0"):
            s.validate()


class TestCalcDissolutionWater:
    def test_calc_dissolution_water(self):
        """Positive inputs produce positive result."""
        result = calc_dissolution_water(
            ore_feed=1000.0,
            alkali_conc=220.0,
            temp=250.0,
        )
        assert isinstance(result, float)
        assert result > 0

    def test_calc_dissolution_water_formula(self):
        """Verify the formula: Q = ore_feed * (2.5 + 0.003*temp) / (1 + alkali_conc/300)."""
        ore_feed = 500.0
        alkali_conc = 150.0
        temp = 200.0
        expected = ore_feed * (2.5 + 0.003 * temp) / (1.0 + alkali_conc / 300.0)
        result = calc_dissolution_water(ore_feed, alkali_conc, temp)
        assert abs(result - expected) < 1e-9

    def test_calc_dissolution_water_zero_feed(self):
        """Zero ore feed gives zero water demand."""
        result = calc_dissolution_water(ore_feed=0.0, alkali_conc=200.0, temp=250.0)
        assert abs(result) < 1e-12

    def test_calc_dissolution_water_negative_feed(self):
        """Negative ore_feed raises ValueError."""
        with pytest.raises(ValueError, match="ore_feed must be >= 0"):
            calc_dissolution_water(ore_feed=-10.0, alkali_conc=200.0, temp=250.0)

    def test_calc_dissolution_water_negative_alkali(self):
        """Negative alkali_conc raises ValueError."""
        with pytest.raises(ValueError, match="alkali_conc must be >= 0"):
            calc_dissolution_water(ore_feed=100.0, alkali_conc=-5.0, temp=250.0)

    def test_calc_dissolution_water_negative_temp(self):
        """Negative temperature raises ValueError."""
        with pytest.raises(ValueError, match="temp must be >= 0"):
            calc_dissolution_water(ore_feed=100.0, alkali_conc=200.0, temp=-10.0)


class TestCalcDecompositionWater:
    def test_calc_decomposition_water(self):
        """Positive inputs produce positive result."""
        result = calc_decomposition_water(
            seed_ratio=3.0,
            temp=60.0,
            tank_volume=500.0,
        )
        assert isinstance(result, float)
        assert result > 0

    def test_calc_decomposition_water_formula(self):
        """Verify the formula: Q = tank_vol * 0.02 * (1 + seed*0.1) * (1 + (temp-50)*0.005)."""
        seed_ratio = 2.0
        temp = 70.0
        tank_volume = 400.0
        expected = tank_volume * 0.02 * (1.0 + seed_ratio * 0.1) * (1.0 + (temp - 50.0) * 0.005)
        result = calc_decomposition_water(seed_ratio, temp, tank_volume)
        assert abs(result - expected) < 1e-9

    def test_calc_decomposition_water_negative_volume(self):
        """Negative tank_volume raises ValueError."""
        with pytest.raises(ValueError, match="tank_volume must be >= 0"):
            calc_decomposition_water(seed_ratio=3.0, temp=60.0, tank_volume=-100.0)


class TestCalcEvaporationMakeup:
    def test_calc_evaporation_makeup(self):
        """Positive inputs produce positive result."""
        result = calc_evaporation_makeup(evap_ratio=0.15, circulation_volume=2000.0)
        assert isinstance(result, float)
        assert result > 0

    def test_calc_evaporation_makeup_formula(self):
        """Verify the formula: Q = circulation_volume * evap_ratio * 0.85."""
        evap_ratio = 0.2
        circ_vol = 1500.0
        expected = circ_vol * evap_ratio * 0.85
        result = calc_evaporation_makeup(evap_ratio, circ_vol)
        assert abs(result - expected) < 1e-9

    def test_calc_evaporation_makeup_negative_ratio(self):
        """Negative evap_ratio raises ValueError."""
        with pytest.raises(ValueError, match="evap_ratio must be >= 0"):
            calc_evaporation_makeup(evap_ratio=-0.1, circulation_volume=2000.0)

    def test_calc_evaporation_makeup_negative_volume(self):
        """Negative circulation_volume raises ValueError."""
        with pytest.raises(ValueError, match="circulation_volume must be >= 0"):
            calc_evaporation_makeup(evap_ratio=0.1, circulation_volume=-100.0)


class TestCalcTotalProcessDemand:
    def test_calc_total_process_demand(self):
        """Returns dict with all workshop keys and total, all positive."""
        state = ProcessState(
            ore_feed_td=1000.0,
            alkali_concentration=220.0,
            dissolution_temp=250.0,
            decomposition_temp=60.0,
            evaporation_ratio=0.15,
        )
        result = calc_total_process_demand(state)

        expected_keys = {
            "ws_dissolution",
            "ws_decomposition",
            "ws_evaporation",
            "ws_red_mud",
            "ws_calcination",
            "total",
        }
        assert set(result.keys()) == expected_keys

        # All values should be positive for this state
        for key in expected_keys:
            assert result[key] > 0, f"{key} should be positive"

        # Total should equal sum of workshops
        workshop_sum = (
            result["ws_dissolution"]
            + result["ws_decomposition"]
            + result["ws_evaporation"]
            + result["ws_red_mud"]
            + result["ws_calcination"]
        )
        assert abs(result["total"] - workshop_sum) < 1e-9

    def test_calc_total_process_demand_zero_state(self):
        """All zeros in state produce all near-zero results (decomposition may be nonzero)."""
        state = ProcessState()  # all defaults are 0.0
        result = calc_total_process_demand(state)

        # Dissolution: ore_feed=0 -> 0
        assert abs(result["ws_dissolution"]) < 1e-12
        # Evaporation: evap_ratio=0 -> 0
        assert abs(result["ws_evaporation"]) < 1e-12
        # Red mud: ore_feed*1.5 = 0
        assert abs(result["ws_red_mud"]) < 1e-12
        # Calcination: ore_feed*0.8 = 0
        assert abs(result["ws_calcination"]) < 1e-12
        # Decomposition: tank_volume*0.02*(1+3*0.1)*(1+(0-50)*0.005) may be nonzero
        # because default seed_ratio=3.0, default tank_volume=500.0, temp=0.0
        # = 500*0.02*(1.3)*(1 + (-50)*0.005) = 500*0.02*1.3*0.75 = 9.75
        assert result["ws_decomposition"] >= 0

    def test_calc_total_process_demand_validates(self):
        """Negative ore_feed should trigger validation error."""
        state = ProcessState(ore_feed_td=-100.0)
        with pytest.raises(ValueError, match="Ore feed rate must be >= 0"):
            calc_total_process_demand(state)

    def test_calc_total_process_demand_red_mud_proportional(self):
        """Red mud water is proportional to ore feed (1.5 m3/t)."""
        state = ProcessState(ore_feed_td=200.0)
        result = calc_total_process_demand(state)
        assert abs(result["ws_red_mud"] - 200.0 * 1.5) < 1e-9

    def test_calc_total_process_demand_calcination_proportional(self):
        """Calcination cooling is proportional to ore feed (0.8 m3/t)."""
        state = ProcessState(ore_feed_td=200.0)
        result = calc_total_process_demand(state)
        assert abs(result["ws_calcination"] - 200.0 * 0.8) < 1e-9
