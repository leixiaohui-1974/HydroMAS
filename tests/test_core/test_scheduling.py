"""Tests for core.scheduling module."""

import pytest
from core.scheduling.rule_based import schedule_rule_based


class TestRuleBasedScheduler:
    def test_emergency_shutoff(self):
        result = schedule_rule_based(current_level=2.0, max_level=1.8)
        assert result["inflow_rate"] == 0.0
        assert result["rule"] == "emergency_shutoff"

    def test_emergency_fill(self):
        result = schedule_rule_based(current_level=0.1, min_level=0.2)
        assert result["inflow_rate"] > 0
        assert result["rule"] == "emergency_fill"

    def test_match_demand(self):
        result = schedule_rule_based(
            current_level=1.0, target_level=1.0, current_demand=0.01
        )
        assert result["inflow_rate"] == 0.01
        assert result["rule"] == "match_demand"

    def test_increase_supply(self):
        result = schedule_rule_based(current_level=0.5, target_level=1.0)
        assert result["rule"] == "increase_supply"

    def test_reduce_supply(self):
        result = schedule_rule_based(current_level=1.5, target_level=1.0)
        assert result["rule"] == "reduce_supply"
