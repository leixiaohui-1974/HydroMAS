"""D2: 氧化铝厂设计场景 — 水网系统设计。
写作 + 建模 + 管理 = MBD设计

验证点：水平衡闭合、12维ODD校核、回用水方案经济性、管网设计。
"""

from __future__ import annotations

import json
from pathlib import Path

from core.water_balance import (
    BalanceNode,
    build_balance_graph,
    calc_full_balance,
    calc_node_residual,
)


class TestDesignAluminaWaterBalance:
    """D2-T1: 全厂水平衡闭合。"""

    def test_single_node_residual_zero(self):
        """单节点：进=出+损耗+蒸发 → 残差=0。"""
        node = BalanceNode(
            node_id="test_node",
            node_type="workshop",
            q_in=100,
            q_out=80,
            q_loss=10,
            q_evap=10,
        )
        residual = calc_node_residual(node)
        assert abs(residual) < 1e-6

    def test_single_node_residual_nonzero(self):
        """单节点有多余流量 → 残差不为零。"""
        node = BalanceNode(
            node_id="leak_node",
            node_type="workshop",
            q_in=100,
            q_out=70,
            q_loss=10,
            q_evap=10,
        )
        residual = calc_node_residual(node)
        # 100 - 70 - 10 - 10 = 10, 有正残差
        assert residual > 0

    def test_balance_graph_construction(self):
        """多节点水平衡图构建。"""
        nodes = [
            BalanceNode(node_id="intake", node_type="intake",
                        q_in=10400, q_out=10400),
            BalanceNode(node_id="workshop", node_type="workshop",
                        q_in=10400, q_out=6200, q_evap=4200),
        ]
        edges = [("intake", "workshop")]
        graph = build_balance_graph(nodes, edges)
        assert graph is not None

    def test_full_balance_calculation(self):
        """全厂水平衡计算。"""
        nodes = [
            BalanceNode(node_id="intake", node_type="intake",
                        q_in=10400, q_out=10400),
            BalanceNode(node_id="workshop", node_type="workshop",
                        q_in=10400, q_out=6200, q_evap=4200),
        ]
        edges = [("intake", "workshop")]
        graph = build_balance_graph(nodes, edges)
        balance = calc_full_balance(graph)
        assert isinstance(balance, dict)


class TestDesignAluminaODD:
    """D2-T2: 12维ODD安全边界校核。"""

    def test_alumina_odd_spec_exists(self):
        """氧化铝ODD规范文件存在。"""
        odd_path = Path("data/alumina_odd_specs.json")
        assert odd_path.exists()
        with open(odd_path) as f:
            specs = json.load(f)
        assert len(specs) > 0

    def test_alumina_odd_check(self):
        """正常参数通过ODD检查。"""
        from mcp_servers.odd_server import check_alumina_odd

        result = check_alumina_odd(current_state={
            "water_level": 0.5,
            "ph": 12.0,
            "temperature": 85,
            "pressure": 3.0,
        })
        assert isinstance(result, dict)
        assert "zone" in result


class TestDesignAluminaReuse:
    """D2-T3: 回用水方案。"""

    def test_reuse_quality_matching(self):
        """水质匹配能产出结果。"""
        from mcp_servers.reuse_server import match_reuse_path

        result = match_reuse_path(
            source_quality={"cod": 30, "turbidity": 10, "ph": 7.0},
            target_requirements=[
                {"workshop_id": "ws_dissolution", "max_cod": 50,
                 "max_turbidity": 20, "demand_m3d": 500},
                {"workshop_id": "ws_calcination", "max_cod": 100,
                 "max_turbidity": 50, "demand_m3d": 300},
            ],
        )
        assert isinstance(result, dict)
        assert "matched_paths" in result
        assert result["n_matched"] > 0


class TestDesignAluminaConfig:
    """D2-T4: 设计配置完整性。"""

    def test_alumina_config_exists(self):
        config_path = Path("data/alumina_config.json")
        assert config_path.exists()
        with open(config_path) as f:
            config = json.load(f)
        assert config["daily_intake_m3"] == 10400

    def test_alumina_config_nodes(self):
        with open("data/alumina_config.json") as f:
            config = json.load(f)
        assert "nodes" in config
        assert len(config["nodes"]) >= 10  # 12+ workshop nodes

    def test_alumina_config_evaporation_sources(self):
        with open("data/alumina_config.json") as f:
            config = json.load(f)
        assert "evaporation_sources" in config
