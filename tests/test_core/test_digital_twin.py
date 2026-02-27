"""Tests for core.simulation.digital_twin module.
core.simulation.digital_twin 模块测试。
"""

import pytest

from core.simulation.digital_twin import _HAS_WNTR, DigitalTwinEngine, TwinState


class TestTwinStateDefaults:
    def test_twin_state_defaults(self):
        """TwinState should initialise with sensible defaults."""
        state = TwinState()
        assert state.timestamp == 0.0
        assert state.node_pressures == {}
        assert state.node_levels == {}
        assert state.pipe_flows == {}
        assert state.pump_speeds == {}


class TestTwinStateValidation:
    def test_twin_state_validate_good(self):
        """Valid TwinState should not raise on validate()."""
        state = TwinState(
            timestamp=10.0,
            node_pressures={"n1": 30.0},
            node_levels={"tank1": 2.5},
            pipe_flows={"p1": 0.05},
            pump_speeds={"pump1": 1.0},
        )
        state.validate()  # should not raise

    def test_twin_state_validate_negative_timestamp(self):
        """Negative timestamp should raise ValueError."""
        state = TwinState(timestamp=-1.0)
        with pytest.raises(ValueError, match="timestamp"):
            state.validate()

    def test_twin_state_validate_bad_pressures_type(self):
        """Non-dict node_pressures should raise ValueError."""
        state = TwinState(node_pressures="bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="node_pressures"):
            state.validate()

    def test_twin_state_validate_bad_levels_type(self):
        """Non-dict node_levels should raise ValueError."""
        state = TwinState(node_levels=[1, 2])  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="node_levels"):
            state.validate()

    def test_twin_state_validate_bad_flows_type(self):
        """Non-dict pipe_flows should raise ValueError."""
        state = TwinState(pipe_flows=42)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="pipe_flows"):
            state.validate()

    def test_twin_state_validate_bad_pump_speeds_type(self):
        """Non-dict pump_speeds should raise ValueError."""
        state = TwinState(pump_speeds="fast")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="pump_speeds"):
            state.validate()


class TestDigitalTwinEngine:
    """Tests using the simplified fallback (no WNTR)."""

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; these test simplified path")
    def test_digital_twin_init(self):
        """DigitalTwinEngine should initialise with empty simplified state."""
        engine = DigitalTwinEngine("nonexistent.inp")
        assert engine._state.timestamp == 0.0
        assert engine._state.node_pressures == {}
        assert engine._state.pipe_flows == {}
        assert engine._use_wntr is False

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; these test simplified path")
    def test_digital_twin_update(self):
        """update() should accept sensor data and return a TwinState."""
        engine = DigitalTwinEngine("test.inp")
        state = engine.update({"sensor_a": 25.0, "sensor_b": 30.0})
        assert isinstance(state, TwinState)
        # New unknown sensors should be stored in node_pressures by default
        assert "sensor_a" in state.node_pressures
        assert "sensor_b" in state.node_pressures
        assert state.timestamp == 1.0

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; these test simplified path")
    def test_digital_twin_update_smoothing(self):
        """Repeated updates should apply exponential smoothing."""
        engine = DigitalTwinEngine("test.inp")
        # First update stores value directly
        engine.update({"s1": 100.0})
        first_val = engine._state.node_pressures["s1"]
        # Second update should smooth toward new value
        engine.update({"s1": 0.0})
        second_val = engine._state.node_pressures["s1"]
        # With smoothing=0.7, second = 0.7 * 0 + 0.3 * first
        expected = 0.7 * 0.0 + 0.3 * first_val
        assert abs(second_val - expected) < 1e-10

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; these test simplified path")
    def test_digital_twin_what_if(self):
        """simulate_what_if should return a list of TwinState snapshots."""
        engine = DigitalTwinEngine("test.inp")
        engine.update({"s1": 50.0})
        states = engine.simulate_what_if(
            scenario={"demand_factor": 1.5, "dt": 100.0},
            horizon=300.0,
        )
        assert isinstance(states, list)
        assert len(states) > 0
        for s in states:
            assert isinstance(s, TwinState)
            assert s.timestamp >= 0.0

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; these test simplified path")
    def test_digital_twin_what_if_bad_horizon(self):
        """simulate_what_if with non-positive horizon should raise ValueError."""
        engine = DigitalTwinEngine("test.inp")
        with pytest.raises(ValueError, match="horizon"):
            engine.simulate_what_if(scenario={}, horizon=-100.0)

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; these test simplified path")
    def test_digital_twin_calibrate(self):
        """calibrate() should return a dict with calibration summary."""
        engine = DigitalTwinEngine("test.inp")
        historical = [
            {"s1": 10.0, "s2": 20.0},
            {"s1": 11.0, "s2": 21.0},
            {"s1": 12.0, "s2": 22.0},
        ]
        result = engine.calibrate(historical)
        assert isinstance(result, dict)
        assert result["n_records"] == 3
        assert "mean_residual" in result
        assert "residuals" in result
        assert len(result["residuals"]) == 3
        assert result["metadata"]["method"] == "simplified_smoothing"

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; these test simplified path")
    def test_digital_twin_calibrate_empty(self):
        """calibrate() with empty historical data should raise ValueError."""
        engine = DigitalTwinEngine("test.inp")
        with pytest.raises(ValueError, match="historical_data must not be empty"):
            engine.calibrate([])

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; these test simplified path")
    def test_digital_twin_timestamp_advances(self):
        """Each update() call should advance the timestamp by 1.0."""
        engine = DigitalTwinEngine("test.inp")
        assert engine._state.timestamp == 0.0
        engine.update({"s1": 1.0})
        assert engine._state.timestamp == 1.0
        engine.update({"s1": 2.0})
        assert engine._state.timestamp == 2.0
        engine.update({"s1": 3.0})
        assert engine._state.timestamp == 3.0
