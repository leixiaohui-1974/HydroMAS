"""Phase 3 tests for SafetyAgent alumina-specific methods.
Phase 3 安全 Agent 氧化铝专用方法测试。

Tests cover check_alumina_state (normal and violation zones),
monitor_pressure_safety, and check_reuse_water_quality.
"""

import pytest
from agents.safety_agent import SafetyAgent


class TestSafetyAgentAlumina:
    """Test alumina-specific safety checks."""

    def setup_method(self):
        self.agent = SafetyAgent()

    # ------------------------------------------------------------------
    # check_alumina_state
    # ------------------------------------------------------------------

    def test_check_alumina_state_normal(self):
        """All values within bounds should yield zone 'normal'."""
        state = {
            "water_level_clear_pool": 4.0,
            "water_level_high_pool": 8.0,
            "intake_flow_total": 400,
            "main_pipe_pressure": 0.35,
            "reuse_water_cod": 25,
            "reuse_water_ph": 7.5,
            "cooling_tower_evap_rate": 150,
            "pump_station_efficiency": 0.75,
            "leak_rate": 0.02,
            "water_balance_residual": 0.01,
            "supply_pressure_cv": 0.08,
            "reuse_water_turbidity": 5,
        }
        result = self.agent.check_alumina_state(state)
        assert isinstance(result, dict)
        assert result["zone"] == "normal"
        assert result["n_violations"] == 0
        assert result["violations"] == []
        assert result["n_checked"] == 12

    def test_check_alumina_state_violation(self):
        """Out-of-bounds value should yield zone 'extended' or 'mrc'."""
        # intake_flow_total is below min (200) but above extended_min (200 - 400*0.1 = 160)
        state = {
            "water_level_clear_pool": 4.0,
            "intake_flow_total": 180,  # below min_value 200, above extended min 160
        }
        result = self.agent.check_alumina_state(state)
        assert isinstance(result, dict)
        assert result["zone"] in ("extended", "mrc")
        assert result["n_violations"] >= 1
        assert len(result["violations"]) >= 1
        # Check the violation details
        violation = result["violations"][0]
        assert "dimension" in violation
        assert "value" in violation
        assert "zone" in violation

    def test_check_alumina_state_mrc_zone(self):
        """Extreme out-of-bounds value should yield zone 'mrc'."""
        # intake_flow_total far below the extended min
        state = {
            "intake_flow_total": 50,  # well below extended_min (160)
        }
        result = self.agent.check_alumina_state(state)
        assert result["zone"] == "mrc"
        assert result["n_violations"] >= 1
        found = [v for v in result["violations"] if v["dimension"] == "intake_flow_total"]
        assert len(found) == 1
        assert found[0]["zone"] == "mrc"

    # ------------------------------------------------------------------
    # monitor_pressure_safety
    # ------------------------------------------------------------------

    def test_monitor_pressure_safety_ok(self):
        """Normal pressures should return safe=True with no violations."""
        pressures = {"pipe_A": 0.3, "pipe_B": 0.45, "pipe_C": 0.25}
        result = self.agent.monitor_pressure_safety(pressures)
        assert isinstance(result, dict)
        assert result["safe"] is True
        assert result["violations"] == []
        assert result["n_checked"] == 3

    def test_monitor_pressure_safety_high(self):
        """High pressure should trigger alarm violation."""
        pressures = {"pipe_A": 0.3, "pipe_B": 0.9}  # 0.9 > 0.8 threshold
        result = self.agent.monitor_pressure_safety(pressures)
        assert result["safe"] is False
        assert len(result["violations"]) >= 1
        high_v = [v for v in result["violations"] if v["issue"] == "high_pressure"]
        assert len(high_v) == 1
        assert high_v[0]["pipe_id"] == "pipe_B"
        assert high_v[0]["severity"] == "high"

    # ------------------------------------------------------------------
    # check_reuse_water_quality
    # ------------------------------------------------------------------

    def test_check_reuse_water_quality_ok(self):
        """Water quality within limits should return quality_ok=True."""
        quality = {"cod": 30, "ph": 7.5, "turbidity": 5}
        result = self.agent.check_reuse_water_quality(quality)
        assert isinstance(result, dict)
        assert result["quality_ok"] is True
        assert result["violations"] == []
        assert result["quality"] == quality

    def test_check_reuse_water_quality_exceed(self):
        """COD exceeding limit should trigger violation."""
        quality = {"cod": 60, "ph": 7.5, "turbidity": 5}  # cod > 50
        result = self.agent.check_reuse_water_quality(quality)
        assert result["quality_ok"] is False
        assert len(result["violations"]) >= 1
        cod_v = [v for v in result["violations"] if v["param"] == "cod"]
        assert len(cod_v) == 1
        assert cod_v[0]["value"] == 60
        assert cod_v[0]["limit"] == 50
        assert cod_v[0]["severity"] == "high"
