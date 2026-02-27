"""O1: 双容水箱运维场景 — 日常运行管理。
写作 + 建模 = 运维

验证点：数字孪生状态估计、四预闭环、告警触发、日报生成。
"""

from __future__ import annotations

import asyncio

from core.odd import check_odd
from core.prediction import predict_linear
from core.simulation import run_simulation


class TestOpsTankMonitoring:
    """O1-T1: 实时监控与状态估计。"""

    def test_simulation_as_realtime_proxy(self):
        """用仿真结果模拟实时数据流。"""
        result = run_simulation(
            duration=5,
            dt=0.1,
            q_in_profile=[(0.0, 0.5), (5.0, 0.5)],
            initial_h=0.5,
            tank_params={"area": 1.0, "cd": 0.6},
        )
        # 运维场景：每步都应有有效数据
        for h in result["water_level"]:
            assert isinstance(h, (int, float))
            assert h >= 0

    def test_odd_continuous_monitoring(self):
        """连续 ODD 监测，正常数据全部正常区。"""
        normal_levels = [0.3, 0.4, 0.5, 0.6, 0.5, 0.4]
        for h in normal_levels:
            r = check_odd({"water_level": h})
            assert r["zone"] == "normal"


class TestOpsTankForecast:
    """O1-T2: 预报/预警（四预闭环前两步）。"""

    def test_predict_linear_returns_values(self):
        historical = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]
        result = predict_linear(historical, horizon=5)
        assert "predictions" in result
        assert len(result["predictions"]) == 5

    def test_warning_on_high_forecast(self):
        """预测液位过高时应触发预警。"""
        # ODD water_level: normal=[0.27, 1.63], extended=(1.63, 1.8], mrc>1.8
        # Use steeply rising data that forecasts above 1.8
        historical = [1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8]
        result = predict_linear(historical, horizon=5)
        forecasted_max = max(result["predictions"])
        # 检查是否有越限趋势
        odd_result = check_odd({"water_level": forecasted_max})
        # 预测值超出ODD上限时应进入扩展区或MRC区
        if forecasted_max > 1.63:
            assert odd_result["zone"] in ("extended", "mrc")


class TestOpsTankWarningSkill:
    """O1-T3: 预警技能端到端。"""

    def test_warning_skill_execute(self):
        from skills.warning_skill import WarningSkill

        skill = WarningSkill()
        # WarningSkill expects a 'forecast' dict with 'predictions' key
        # or 'historical_data' to generate forecast from
        result = asyncio.get_event_loop().run_until_complete(
            skill.execute({
                "forecast": {
                    "predictions": [0.8, 0.85, 0.9, 0.95, 1.0, 1.5, 1.7, 1.9],
                    "confidence_upper": [0.85, 0.9, 0.95, 1.0, 1.05, 1.55, 1.75, 1.95],
                    "confidence_lower": [0.75, 0.8, 0.85, 0.9, 0.95, 1.45, 1.65, 1.85],
                    "horizon": 8,
                },
            })
        )
        assert result.success


class TestOpsTankDailyReport:
    """O1-T4: 日报自动生成。"""

    def test_daily_report_skill(self):
        from skills.daily_report import DailyReportSkill

        skill = DailyReportSkill()
        # DailyReportSkill requires nodes_data and edges_data for water balance
        nodes_data = [
            {"node_id": "intake", "node_type": "intake",
             "q_in": 10400, "q_out": 10400, "q_loss": 0, "q_evap": 0},
            {"node_id": "workshop", "node_type": "workshop",
             "q_in": 10400, "q_out": 6200, "q_loss": 0, "q_evap": 4200},
        ]
        edges_data = [["intake", "workshop"]]
        result = asyncio.get_event_loop().run_until_complete(
            skill.execute({
                "date": "2026-02-27",
                "nodes_data": nodes_data,
                "edges_data": edges_data,
            })
        )
        assert result.success
        assert "report_markdown" in result.data or "report" in result.data


class TestOpsTankSafety:
    """O1-T5: 安全Agent监护。"""

    def test_safety_agent_check_normal(self):
        from agents.safety_agent import SafetyAgent

        sa = SafetyAgent()
        result = sa.check_state({"water_level": 0.5})
        assert result["zone"] == "normal"

    def test_safety_agent_check_violation(self):
        from agents.safety_agent import SafetyAgent

        sa = SafetyAgent()
        result = sa.check_state({"water_level": 100.0})
        assert result["zone"] == "mrc"
