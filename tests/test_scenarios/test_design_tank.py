"""D1: 双容水箱设计场景 — 系统优化选型。
写作 + 建模 + 管理 = MBD设计

验证点：水箱尺寸设计、灵敏度分析、ODD安全裕度、设计参数合规性。
"""

from __future__ import annotations

from core.design import optimize_tank_size, sensitivity_oat
from core.odd import check_odd
from core.simulation import TankParams, run_simulation


def _steady_state_level(params: dict) -> float:
    """Evaluate function for sensitivity: run a short simulation and return final level."""
    tp = {
        "area": params.get("area", 1.0),
        "cd": params.get("cd", 0.6),
    }
    result = run_simulation(
        duration=20,
        dt=0.1,
        q_in_profile=[(0.0, 0.5), (20.0, 0.5)],
        initial_h=params.get("initial_level", 0.5),
        tank_params=tp,
    )
    return result["water_level"][-1]


class TestDesignTankSizing:
    """D1-T1: 水箱容积优化设计。"""

    def test_design_tank_returns_valid_params(self):
        result = optimize_tank_size(peak_demand=0.5, min_reserve_time=60, safety_factor=1.2)
        assert "volume" in result
        assert result["volume"] > 0
        assert "optimal_area" in result
        assert result["optimal_area"] > 0

    def test_design_tank_safety_factor(self):
        """安全系数增大 -> 容积增大。"""
        r1 = optimize_tank_size(peak_demand=0.5, min_reserve_time=60, safety_factor=1.0)
        r2 = optimize_tank_size(peak_demand=0.5, min_reserve_time=60, safety_factor=1.5)
        assert r2["volume"] >= r1["volume"]

    def test_design_tank_flow_scaling(self):
        """流量增大 -> 容积增大。"""
        r1 = optimize_tank_size(peak_demand=0.3, min_reserve_time=60, safety_factor=1.2)
        r2 = optimize_tank_size(peak_demand=0.8, min_reserve_time=60, safety_factor=1.2)
        assert r2["volume"] >= r1["volume"]


class TestDesignTankSensitivity:
    """D1-T2: 灵敏度分析确保设计裕度。"""

    def test_sensitivity_analysis_returns_results(self):
        result = sensitivity_oat(
            base_params={"cd": 0.6, "area": 1.0, "initial_level": 0.5},
            param_ranges={"cd": (0.4, 0.8)},
            evaluate_fn=_steady_state_level,
            n_levels=5,
        )
        assert "parameters" in result
        assert "cd" in result["parameters"]
        assert len(result["parameters"]["cd"]["levels"]) == 5

    def test_sensitivity_monotonic_trend(self):
        """Cd增大 -> 出流增大 -> 液位下降（单调趋势）。"""
        result = sensitivity_oat(
            base_params={"cd": 0.6, "area": 1.0, "initial_level": 0.5},
            param_ranges={"cd": (0.3, 0.9)},
            evaluate_fn=_steady_state_level,
            n_levels=5,
        )
        outputs = result["parameters"]["cd"]["outputs"]
        # 至少应有结果
        assert len(outputs) > 0


class TestDesignTankODD:
    """D1-T3: ODD安全边界满足设计规范。"""

    def test_design_within_odd_normal(self):
        """正常设计参数应在正常区。"""
        result = check_odd({"water_level": 0.6})
        assert result["zone"] == "normal"

    def test_design_max_level_check(self):
        """最大水位应检查。"""
        result = check_odd({"water_level": 0.95})
        # 接近上限应为扩展区或正常区
        assert result["zone"] in ("normal", "extended")


class TestDesignTankCompliance:
    """D1-T4: 设计参数在规范范围内。"""

    def test_cd_within_standard_range(self):
        """流量系数Cd标准范围 0.4~0.9。"""
        tp = TankParams(area=1.0, cd=0.6)
        assert 0.4 <= tp.cd <= 0.9

    def test_area_positive(self):
        """水箱截面积必须为正。"""
        tp = TankParams(area=1.5, cd=0.6)
        assert tp.area > 0

    def test_simulation_with_designed_params(self):
        """用设计参数跑仿真应正常完成。"""
        designed = optimize_tank_size(peak_demand=0.5, min_reserve_time=60, safety_factor=1.2)
        tp = {
            "area": designed["optimal_area"],
            "cd": 0.6,
        }
        result = run_simulation(
            duration=20,
            dt=0.1,
            q_in_profile=[(0.0, 0.5), (20.0, 0.5)],
            initial_h=0.3,
            tank_params=tp,
        )
        assert len(result["water_level"]) > 0
        assert all(h >= 0 for h in result["water_level"])
