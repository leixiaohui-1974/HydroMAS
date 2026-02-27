"""Balance graph — plant-wide water network topology and full balance.
平衡图 — 全厂水网拓扑与整体水平衡计算。

Builds a directed graph of BalanceNode instances connected by edges,
then computes plant-wide balance metrics. Uses networkx when available,
falls back to a pure-dict representation otherwise.
"""

from __future__ import annotations

import logging
from typing import Any

from core.water_balance.node_balance import BalanceNode, calc_node_residual, calc_reuse_rate

logger = logging.getLogger(__name__)

try:
    import networkx as nx

    _HAS_NX = True
except ImportError:  # pragma: no cover
    _HAS_NX = False


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph_nx(
    nodes: list[BalanceNode],
    edges: list[tuple[str, str]],
) -> Any:
    """Build a networkx DiGraph with node attributes.
    使用 networkx 构建有向图（含节点属性）。
    """
    graph = nx.DiGraph()
    for node in nodes:
        graph.add_node(node.node_id, balance_node=node)
    for src, dst in edges:
        if src not in graph:
            raise ValueError(f"Edge source '{src}' not found in nodes")
        if dst not in graph:
            raise ValueError(f"Edge destination '{dst}' not found in nodes")
        graph.add_edge(src, dst)
    return graph


def _build_graph_dict(
    nodes: list[BalanceNode],
    edges: list[tuple[str, str]],
) -> dict:
    """Build a pure-dict graph representation (networkx fallback).
    构建纯字典图表示（networkx 回退方案）。
    """
    node_map: dict[str, BalanceNode] = {}
    for node in nodes:
        node_map[node.node_id] = node

    adjacency: dict[str, list[str]] = {nid: [] for nid in node_map}
    for src, dst in edges:
        if src not in node_map:
            raise ValueError(f"Edge source '{src}' not found in nodes")
        if dst not in node_map:
            raise ValueError(f"Edge destination '{dst}' not found in nodes")
        adjacency[src].append(dst)

    return {
        "nodes": node_map,
        "edges": list(edges),
        "adjacency": adjacency,
    }


def build_balance_graph(
    nodes: list[BalanceNode],
    edges: list[tuple[str, str]],
) -> dict | Any:
    """Build a directed balance graph from nodes and edges.
    根据节点和边构建有向水平衡图。

    When *networkx* is installed the return value is a ``nx.DiGraph`` with
    each node carrying a ``balance_node`` attribute.  Otherwise a plain
    dict is returned with keys ``nodes``, ``edges``, and ``adjacency``.

    Args:
        nodes: List of BalanceNode instances / 平衡节点列表
        edges: List of (source_id, destination_id) tuples / 边列表

    Returns:
        nx.DiGraph or dict representing the balance network.
        有向图（nx.DiGraph）或字典表示的水平衡网络。
    """
    if _HAS_NX:
        return _build_graph_nx(nodes, edges)
    return _build_graph_dict(nodes, edges)


# ---------------------------------------------------------------------------
# Helpers to abstract over the two representations
# ---------------------------------------------------------------------------

def _iter_nodes(graph: Any) -> list[BalanceNode]:
    """Extract BalanceNode list from either representation."""
    if _HAS_NX and isinstance(graph, nx.DiGraph):
        return [graph.nodes[n]["balance_node"] for n in graph.nodes]
    return list(graph["nodes"].values())


def _edge_count(graph: Any) -> int:
    """Return the number of edges."""
    if _HAS_NX and isinstance(graph, nx.DiGraph):
        return graph.number_of_edges()
    return len(graph["edges"])


# ---------------------------------------------------------------------------
# Full balance calculation
# ---------------------------------------------------------------------------

def calc_full_balance(graph: Any) -> dict:
    """Calculate plant-wide water balance from the graph.
    根据图计算全厂水平衡。

    Aggregates per-node residuals and derives plant-wide totals including
    reuse rate and overall balance error.

    Args:
        graph: Balance graph (nx.DiGraph or dict) / 水平衡图

    Returns:
        Dict with keys: node_residuals, total_intake, total_consumption,
        total_loss, total_evap, reuse_rate, balance_error.
        字典，包含节点残差、总取水量、总消耗量、总漏损、总蒸发、
        回用率、平衡误差。
    """
    nodes = _iter_nodes(graph)

    node_residuals: dict[str, float] = {}
    total_intake = 0.0
    total_consumption = 0.0
    total_loss = 0.0
    total_evap = 0.0
    total_reuse = 0.0

    for node in nodes:
        residual = calc_node_residual(node)
        node_residuals[node.node_id] = residual

        if node.node_type == "intake":
            total_intake += node.q_in
        if node.node_type == "reuse":
            total_reuse += node.q_in

        total_consumption += node.q_out
        total_loss += node.q_loss
        total_evap += node.q_evap

    reuse_rate = calc_reuse_rate(total_reuse, total_intake)

    # Overall balance error: sum of absolute residuals
    balance_error = sum(abs(r) for r in node_residuals.values())

    return {
        "node_residuals": node_residuals,
        "total_intake": total_intake,
        "total_consumption": total_consumption,
        "total_loss": total_loss,
        "total_evap": total_evap,
        "reuse_rate": reuse_rate,
        "balance_error": balance_error,
    }


def get_graph_summary(graph: Any) -> dict:
    """Get a summary of the balance graph structure and totals.
    获取水平衡图结构与汇总信息。

    Args:
        graph: Balance graph (nx.DiGraph or dict) / 水平衡图

    Returns:
        Dict with keys: n_nodes, n_edges, node_types_count,
        total_intake, total_consumption.
        字典，包含节点数、边数、各类型节点计数、总取水量、总消耗量。
    """
    nodes = _iter_nodes(graph)

    node_types_count: dict[str, int] = {}
    total_intake = 0.0
    total_consumption = 0.0

    for node in nodes:
        node_types_count[node.node_type] = node_types_count.get(node.node_type, 0) + 1
        if node.node_type == "intake":
            total_intake += node.q_in
        total_consumption += node.q_out

    return {
        "n_nodes": len(nodes),
        "n_edges": _edge_count(graph),
        "node_types_count": node_types_count,
        "total_intake": total_intake,
        "total_consumption": total_consumption,
    }
