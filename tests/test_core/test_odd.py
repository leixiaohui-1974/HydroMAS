"""Tests for core.odd module."""

import pytest

from core.odd.mrc_handler import determine_mrc_actions, generate_mrc_plan
from core.odd.odd_definition import (
    DimensionSpec,
    ODDSpec,
    create_tank_odd,
)
from core.odd.odd_monitor import check_odd, check_odd_series, classify_value


class TestODDDefinition:
    def test_dimension_spec(self):
        d = DimensionSpec(name="water_level", min_value=0.1, max_value=1.8, unit="m")
        assert d.warning_lower == pytest.approx(0.27, abs=0.01)
        assert d.warning_upper == pytest.approx(1.63, abs=0.01)

    def test_create_tank_odd(self):
        odd = create_tank_odd()
        assert len(odd.dimensions) == 6
        wl = odd.get_dimension("water_level")
        assert wl is not None
        assert wl.min_value == 0.1
        assert wl.max_value == 1.8

    def test_to_from_dict(self):
        odd = create_tank_odd()
        d = odd.to_dict()
        odd2 = ODDSpec.from_dict(d)
        assert len(odd2.dimensions) == len(odd.dimensions)


class TestODDMonitor:
    def test_classify_normal(self):
        d = DimensionSpec("wl", 0.1, 1.8, "m", warning_margin=0.1)
        assert classify_value(1.0, d) == "normal"

    def test_classify_extended(self):
        d = DimensionSpec("wl", 0.1, 1.8, "m", warning_margin=0.1)
        assert classify_value(0.15, d) == "extended"

    def test_classify_mrc(self):
        d = DimensionSpec("wl", 0.1, 1.8, "m", warning_margin=0.1)
        assert classify_value(2.0, d) == "mrc"

    def test_check_odd_normal(self):
        result = check_odd({"water_level": 1.0, "inflow_rate": 0.02})
        assert result["zone"] == "normal"
        assert result["n_violations"] == 0

    def test_check_odd_mrc(self):
        result = check_odd({"water_level": 2.5})
        assert result["zone"] == "mrc"
        assert result["n_violations"] == 1

    def test_check_odd_series(self):
        states = [
            {"water_level": 1.0},
            {"water_level": 1.5},
            {"water_level": 2.0},  # mrc
        ]
        result = check_odd_series(states, [0.0, 1.0, 2.0])
        assert result["worst_zone"] == "mrc"
        assert result["time_to_breach"] == 2.0


class TestMRCHandler:
    def test_water_level_upper(self):
        violations = [{
            "dimension": "water_level",
            "bound_violated": "upper",
            "value": 2.0, "limit": 1.8,
        }]
        actions = determine_mrc_actions(violations)
        assert len(actions) >= 1
        assert any(a["action"] == "close_inlet" for a in actions)

    def test_structural_pressure(self):
        violations = [{
            "dimension": "structural_pressure",
            "bound_violated": "upper",
            "value": 60, "limit": 50,
        }]
        actions = determine_mrc_actions(violations)
        assert any(a["action"] == "emergency_stop" for a in actions)

    def test_generate_mrc_plan(self):
        violations = [{
            "dimension": "water_level",
            "bound_violated": "upper",
            "value": 2.0, "limit": 1.8,
        }]
        plan = generate_mrc_plan(
            violations, {"water_level": 2.0},
        )
        assert plan["status"] == "mrc_activated"
        assert len(plan["actions"]) >= 1
