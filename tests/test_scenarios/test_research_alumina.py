"""R2: 氧化铝厂科研场景 — 多源蒸发耦合优化研究。
写作 + 建模 + 管理 = 科研

验证点：Merkel蒸发模型、焙烧蒸发、赤泥蒸发、全厂蒸发汇总、优化建议。
"""

from __future__ import annotations

import asyncio

from core.evaporation import (
    CalcinationParams,
    CoolingTowerParams,
    RedMudParams,
    calc_calcination_evap,
    calc_evaporation_merkel,
    calc_red_mud_water,
)


class TestResearchAluminaMerkel:
    """R2-T1: Merkel蒸发模型物理合理性。"""

    def test_merkel_basic_output(self):
        ct = CoolingTowerParams(
            water_flow_m3h=1000,
            t_in=42,
            t_out=32,
        )
        weather = {"t_db": 30, "t_wb": 28, "wind_speed": 2.0}
        evap = calc_evaporation_merkel(ct, weather)
        assert isinstance(evap, dict)
        assert evap["evap_rate_m3h"] > 0

    def test_merkel_evap_less_than_flow(self):
        """蒸发量不应超过入水量。"""
        ct = CoolingTowerParams(
            water_flow_m3h=1000,
            t_in=42,
            t_out=32,
        )
        weather = {"t_db": 30, "t_wb": 28, "wind_speed": 2.0}
        evap = calc_evaporation_merkel(ct, weather)
        assert evap["evap_rate_m3h"] < ct.water_flow_m3h

    def test_merkel_increases_with_delta_t(self):
        """温差增大 → 蒸发量增大。"""
        weather = {"t_db": 30, "t_wb": 28, "wind_speed": 2.0}
        ct1 = CoolingTowerParams(
            water_flow_m3h=1000, t_in=38, t_out=32,
        )
        ct2 = CoolingTowerParams(
            water_flow_m3h=1000, t_in=48, t_out=32,
        )
        e1 = calc_evaporation_merkel(ct1, weather)
        e2 = calc_evaporation_merkel(ct2, weather)
        assert e2["evap_rate_m3h"] > e1["evap_rate_m3h"]

    def test_merkel_reproducibility(self):
        """相同参数两次计算结果一致（科研可重复性）。"""
        ct = CoolingTowerParams(
            water_flow_m3h=1000, t_in=42, t_out=32,
        )
        weather = {"t_db": 30, "t_wb": 28, "wind_speed": 2.0}
        e1 = calc_evaporation_merkel(ct, weather)
        e2 = calc_evaporation_merkel(ct, weather)
        assert e1["evap_rate_m3h"] == e2["evap_rate_m3h"]


class TestResearchAluminaCalcination:
    """R2-T2: 焙烧蒸发模型。"""

    def test_calcination_evap_positive(self):
        params = CalcinationParams(
            slurry_flow_m3h=50,
            moisture_content=0.45,
            calcination_temp=1050,
        )
        evap = calc_calcination_evap(params)
        assert isinstance(evap, dict)
        assert evap["evap_rate_m3h"] > 0

    def test_calcination_evap_monotonic(self):
        """含水率增大 → 蒸发量增大。"""
        p1 = CalcinationParams(
            slurry_flow_m3h=50, moisture_content=0.30, calcination_temp=1050,
        )
        p2 = CalcinationParams(
            slurry_flow_m3h=50, moisture_content=0.55, calcination_temp=1050,
        )
        e1 = calc_calcination_evap(p1)
        e2 = calc_calcination_evap(p2)
        assert e2["evap_rate_m3h"] > e1["evap_rate_m3h"]


class TestResearchAluminaRedMud:
    """R2-T3: 赤泥带水模型。"""

    def test_red_mud_water_positive(self):
        params = RedMudParams(
            mud_dry_mass_td=500,
            moisture_ratio=0.55,
        )
        result = calc_red_mud_water(params)
        assert isinstance(result, dict)
        assert result["water_carry_m3d"] > 0

    def test_red_mud_scales_with_mass(self):
        """干泥量增大 → 带水量增大。"""
        p1 = RedMudParams(mud_dry_mass_td=300, moisture_ratio=0.55)
        p2 = RedMudParams(mud_dry_mass_td=700, moisture_ratio=0.55)
        w1 = calc_red_mud_water(p1)
        w2 = calc_red_mud_water(p2)
        assert w2["water_carry_m3d"] > w1["water_carry_m3d"]


class TestResearchAluminaEvapSkill:
    """R2-T4: 全厂蒸发优化技能。"""

    def test_evap_optimization_skill(self):
        from skills.evap_optimization import EvapOptimizationSkill

        skill = EvapOptimizationSkill()
        result = asyncio.get_event_loop().run_until_complete(
            skill.execute({
                "tower_params": {
                    "water_flow_m3h": 500,
                    "t_in": 42,
                    "t_out": 32,
                },
            })
        )
        assert result.success


class TestResearchAluminaAnalysis:
    """R2-T5: 分析Agent方案比较能力。"""

    def test_analysis_agent_compare_schemes(self):
        from agents.analysis_agent import AnalysisAgent

        agent = AnalysisAgent()
        result = asyncio.get_event_loop().run_until_complete(
            agent.compare_schemes(
                schemes=[
                    {"duration": 10, "dt": 0.1,
                     "q_in_profile": [(0.0, 0.5), (10.0, 0.5)],
                     "initial_h": 0.5,
                     "tank_params": {"area": 1.0, "cd": 0.6}},
                    {"duration": 10, "dt": 0.1,
                     "q_in_profile": [(0.0, 0.5), (10.0, 0.5)],
                     "initial_h": 0.5,
                     "tank_params": {"area": 1.5, "cd": 0.6}},
                ],
                metrics=["max_level", "min_level"],
            )
        )
        assert isinstance(result, dict)
        assert "ranking" in result or "comparison" in result or len(result) > 0
