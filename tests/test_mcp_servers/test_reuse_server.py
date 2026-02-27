"""Integration tests for MCP reuse water server."""

import pytest

from mcp_servers.reuse_server import (
    evaluate_reuse_benefit,
    match_reuse_path,
    optimize_reuse_schedule,
)

# ---------------------------------------------------------------------------
# Shared test data helpers
# ---------------------------------------------------------------------------

def _good_source_quality():
    """Return source water quality that meets typical workshop limits."""
    return {
        "cod": 20.0,
        "ph": 7.0,
        "turbidity": 5.0,
        "conductivity": 300.0,
    }


def _poor_source_quality():
    """Return source water quality that exceeds most workshop limits."""
    return {
        "cod": 500.0,
        "ph": 3.0,
        "turbidity": 200.0,
        "conductivity": 5000.0,
    }


def _target_requirements():
    """Return a list of workshop requirements with varying strictness."""
    return [
        {
            "workshop_id": "ws_cooling",
            "max_cod": 50.0,
            "max_turbidity": 10.0,
            "demand_m3d": 100.0,
        },
        {
            "workshop_id": "ws_washing",
            "max_cod": 30.0,
            "max_turbidity": 8.0,
            "demand_m3d": 80.0,
        },
        {
            "workshop_id": "ws_boiler",
            "max_cod": 10.0,
            "max_turbidity": 2.0,
            "demand_m3d": 50.0,
        },
    ]


class TestMatchReusePath:
    def test_match_reuse_path(self):
        """Good quality source matches workshops whose limits are above it."""
        result = match_reuse_path(
            source_quality=_good_source_quality(),
            target_requirements=_target_requirements(),
        )
        assert isinstance(result, dict)
        assert "matched_paths" in result
        assert "unmatched" in result
        assert "n_matched" in result
        assert "n_unmatched" in result
        assert "source_quality" in result
        # COD=20 <= 50 and turbidity=5 <= 10  -> ws_cooling matched
        # COD=20 <= 30 and turbidity=5 <= 8   -> ws_washing matched
        # COD=20 > 10                          -> ws_boiler NOT matched
        assert result["n_matched"] == 2
        assert result["n_unmatched"] == 1
        matched_ids = [p["workshop_id"] for p in result["matched_paths"]]
        assert "ws_cooling" in matched_ids
        assert "ws_washing" in matched_ids

    def test_match_reuse_path_no_match(self):
        """Poor quality source matches no workshop."""
        result = match_reuse_path(
            source_quality=_poor_source_quality(),
            target_requirements=_target_requirements(),
        )
        assert result["n_matched"] == 0
        assert result["n_unmatched"] == 3
        assert len(result["matched_paths"]) == 0
        # Every unmatched entry should contain rejection reasons
        for entry in result["unmatched"]:
            assert "rejection_reasons" in entry
            assert len(entry["rejection_reasons"]) > 0


class TestOptimizeReuseSchedule:
    def test_optimize_reuse_schedule(self):
        """Valid sources and demands return a schedule with reuse volume."""
        sources = [
            {
                "source_id": "src_A",
                "capacity_m3d": 200.0,
                "cod": 15.0,
                "turbidity": 4.0,
            },
        ]
        demands = [
            {
                "workshop_id": "ws_cooling",
                "demand_m3d": 100.0,
                "max_cod": 50.0,
                "max_turbidity": 10.0,
            },
            {
                "workshop_id": "ws_washing",
                "demand_m3d": 80.0,
                "max_cod": 30.0,
                "max_turbidity": 8.0,
            },
        ]
        result = optimize_reuse_schedule(
            sources=sources,
            demands=demands,
        )
        assert isinstance(result, dict)
        assert "schedule" in result
        assert "total_reuse_m3d" in result
        assert "total_demand_m3d" in result
        assert "reuse_rate" in result
        assert "status" in result
        assert "method" in result
        # Source quality meets both demands and capacity=200 covers 100+80=180
        assert result["total_reuse_m3d"] == pytest.approx(180.0, abs=1.0)
        assert result["total_demand_m3d"] == pytest.approx(180.0)
        assert result["reuse_rate"] == pytest.approx(1.0, abs=0.01)
        assert len(result["schedule"]) >= 1

    def test_optimize_reuse_schedule_empty(self):
        """Empty sources list raises ValueError."""
        with pytest.raises(ValueError, match="sources must be a non-empty list"):
            optimize_reuse_schedule(
                sources=[],
                demands=[
                    {
                        "workshop_id": "ws_1",
                        "demand_m3d": 100.0,
                        "max_cod": 50.0,
                        "max_turbidity": 10.0,
                    },
                ],
            )


class TestEvaluateReuseBenefit:
    def test_evaluate_reuse_benefit(self):
        """Optimized reuse above current rate yields positive savings."""
        optimized_reuse = {
            "total_reuse_m3d": 150.0,
            "total_demand_m3d": 200.0,
        }
        result = evaluate_reuse_benefit(
            current_reuse_rate=0.5,
            optimized_reuse=optimized_reuse,
            water_price=4.0,
        )
        assert isinstance(result, dict)
        assert "new_reuse_rate" in result
        assert "improvement" in result
        assert "daily_savings_m3" in result
        assert "annual_savings_m3" in result
        assert "daily_cost_saving_cny" in result
        assert "annual_cost_saving_cny" in result
        # new_reuse_rate = 150/200 = 0.75
        assert result["new_reuse_rate"] == pytest.approx(0.75)
        # improvement = 0.75 - 0.5 = 0.25
        assert result["improvement"] == pytest.approx(0.25)
        # baseline_reuse = 0.5 * 200 = 100, daily_savings = 150 - 100 = 50
        assert result["daily_savings_m3"] == pytest.approx(50.0)
        # annual = 50 * 365 = 18250
        assert result["annual_savings_m3"] == pytest.approx(18250.0)
        # cost = 50 * 4 = 200 per day
        assert result["daily_cost_saving_cny"] == pytest.approx(200.0)
        # annual cost = 18250 * 4 = 73000
        assert result["annual_cost_saving_cny"] == pytest.approx(73000.0)

    def test_evaluate_reuse_benefit_no_improvement(self):
        """When optimized reuse equals current rate, savings are zero."""
        optimized_reuse = {
            "total_reuse_m3d": 100.0,
            "total_demand_m3d": 200.0,
        }
        result = evaluate_reuse_benefit(
            current_reuse_rate=0.5,
            optimized_reuse=optimized_reuse,
            water_price=4.0,
        )
        # new_reuse_rate = 100/200 = 0.5 = current_reuse_rate
        assert result["new_reuse_rate"] == pytest.approx(0.5)
        assert result["improvement"] == pytest.approx(0.0)
        assert result["daily_savings_m3"] == pytest.approx(0.0)
        assert result["annual_savings_m3"] == pytest.approx(0.0)
        assert result["daily_cost_saving_cny"] == pytest.approx(0.0)
        assert result["annual_cost_saving_cny"] == pytest.approx(0.0)
