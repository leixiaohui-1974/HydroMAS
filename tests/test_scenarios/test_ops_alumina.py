"""O2: 氧化铝厂运维场景 — 水网日常运维。
写作 + 建模 = 运维

验证点：泄漏检测、全局调度、蒸发监控、KPI评估、日报生成。
"""

from __future__ import annotations

import asyncio

# ---- Shared test data ----

_SAMPLE_NODES_DATA = [
    {"node_id": "intake", "node_type": "intake",
     "q_in": 10400, "q_out": 10400},
    {"node_id": "workshop", "node_type": "workshop",
     "q_in": 10400, "q_out": 6200, "q_evap": 4200},
]

_SAMPLE_EDGES_DATA = [
    ("intake", "workshop"),
]


class TestOpsAluminaLeakDetection:
    """O2-T1: 泄漏检测端到端。"""

    def test_leak_detection_mcp(self):
        """MCP层泄漏检测工具可调用。"""
        from mcp_servers.leak_detection_server import detect_leak

        # detect_leak requires graph_data with nodes having 'features' key
        graph_data = {
            "nodes": {
                "n1": {"features": [3.0, 100, 0.5]},
                "n2": {"features": [2.8, 95, 0.4]},
                "n3": {"features": [2.5, 90, 0.3]},
            },
            "edges": [("n1", "n2"), ("n2", "n3")],
            "adjacency": {"n1": ["n2"], "n2": ["n1", "n3"], "n3": ["n2"]},
        }
        result = detect_leak(graph_data)
        assert isinstance(result, dict)
        assert "leak_detected" in result


class TestOpsAluminaDispatch:
    """O2-T2: 全局调度方案生成。"""

    def test_rl_dispatch_agent(self):
        """RL调度Agent基本功能。"""
        from agents.rl_dispatch_agent import (
            DispatchAction,
            DispatchState,
            RLDispatchAgent,
        )

        agent = RLDispatchAgent()
        state = DispatchState(
            tank_levels=[3.0, 3.0, 3.0],
            demands=[100, 120, 90],
        )
        action = agent.get_action(state)
        assert isinstance(action, DispatchAction)


class TestOpsAluminaEvapMonitor:
    """O2-T3: 蒸发实时监控。"""

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


class TestOpsAluminaKPI:
    """O2-T4: KPI指标评估。"""

    def test_water_kpi_evaluation(self):
        from mcp_servers.evaluation_server import evaluate_water_kpi

        kpi = evaluate_water_kpi(
            balance_data={
                "reuse_rate": 0.36,
                "leak_rate": 0.02,
                "total_intake": 10400,
                "alumina_output_td": 2000,
                "pump_efficiency": 0.75,
                "balance_error": 0.001,
            },
        )
        assert isinstance(kpi, dict)
        assert "reuse_rate" in kpi
        assert kpi["reuse_rate"] > 0


class TestOpsAluminaDailyReport:
    """O2-T5: 日报自动生成。"""

    def test_report_agent_daily(self):
        """ReportAgent日报输出包含关键内容。"""
        from agents.report_agent import ReportAgent

        agent = ReportAgent()
        report = agent.generate_daily_operation_report({
            "date": "2026-02-27",
            "total_intake": 10400,
            "evaporation": {"total_daily_m3": 4200},
            "reuse": 3744,
        })
        assert isinstance(report, str)
        assert len(report) > 50


class TestOpsAluminaSafety:
    """O2-T6: 安全Agent氧化铝扩展。"""

    def test_safety_agent_alumina(self):
        from agents.safety_agent import SafetyAgent

        sa = SafetyAgent()
        result = sa.check_alumina_state({
            "water_level": 0.5,
            "ph": 12.0,
            "temperature": 85,
            "pressure": 3.0,
            "flow_rate": 500,
        })
        assert isinstance(result, dict)
