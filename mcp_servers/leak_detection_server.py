"""MCP Server: Leak detection tools.
MCP 服务器：泄漏检测工具。

Exposes network graph building, GNN-based leak detection, leak localization,
and acoustic-hydraulic evidence fusion as MCP tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-LeakDetection")


@mcp.tool()
def build_network_graph(
    nodes: list[dict],
    edges: list[dict],
) -> dict:
    """Build a pipe-network graph from nodes and edges via graph_builder.
    通过 graph_builder 从节点和边构建管网图。

    Args:
        nodes: List of node dicts, each with 'id' and 'features' keys.
               features = [flow, pressure, residual].
               节点列表，每个包含 'id' 和 'features' 键。
               features = [流量, 压力, 残差]
        edges: List of edge dicts, each with 'source', 'target', and
               'features' keys. features = [length, diameter, material_code].
               边列表，每个包含 'source'、'target' 和 'features' 键。
               features = [长度, 管径, 材质码]

    Returns:
        Dict with 'nodes', 'edges', and 'adjacency' representing the graph.
        包含 'nodes'、'edges' 和 'adjacency' 的字典图。
    """
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("nodes must be a non-empty list of dicts")
    if not isinstance(edges, list):
        raise ValueError("edges must be a list of edge dicts")

    for i, n in enumerate(nodes):
        if "id" not in n:
            raise ValueError(f"nodes[{i}] must have an 'id' key, got {n!r}")
        if "features" not in n:
            raise ValueError(
                f"nodes[{i}] must have a 'features' key, got {n!r}"
            )

    for j, e in enumerate(edges):
        if "source" not in e or "target" not in e:
            raise ValueError(
                f"edges[{j}] must have 'source' and 'target' keys, got {e!r}"
            )
        if "features" not in e:
            raise ValueError(
                f"edges[{j}] must have a 'features' key, got {e!r}"
            )

    from core.detection import network_to_dict_graph

    return network_to_dict_graph(nodes, edges)


@mcp.tool()
def detect_leak(
    graph_data: dict,
    model_path: str | None = None,
    threshold: float = 0.95,
) -> dict:
    """Run leak detection on a graph snapshot (GNN or statistical fallback).
    在管网图快照上执行泄漏检测（GNN 或统计退化方法）。

    When torch is available and *model_path* is provided, runs the GNN
    model.  Otherwise, falls back to statistical anomaly detection on
    node features.

    Args:
        graph_data: Dict-graph from ``build_network_graph`` containing
                    'nodes', 'edges', and 'adjacency'.
                    由 ``build_network_graph`` 产生的字典图。
        model_path: Optional path to a trained GNN model checkpoint.
                    可选的训练 GNN 模型检查点路径。
        threshold: Anomaly score threshold for leak flag (0-1) /
                   泄漏标志的异常分数阈值

    Returns:
        Dict with leak_detected (bool), anomaly_scores ({node_id: score}),
        and max_score (float).
        包含 leak_detected、anomaly_scores 和 max_score 的字典。
    """
    if not isinstance(graph_data, dict):
        raise ValueError("graph_data must be a dict")
    if "nodes" not in graph_data:
        raise ValueError("graph_data must contain 'nodes' key")
    if threshold < 0 or threshold > 1:
        raise ValueError(f"threshold must be in [0, 1], got {threshold}")

    from core.detection import detect_leak as _detect_leak

    return _detect_leak(
        graph_data=graph_data,
        model_path=model_path,
        threshold=threshold,
    )


@mcp.tool()
def localize_leak(
    graph_data: dict,
    anomaly_scores: dict,
    top_k: int = 3,
) -> dict:
    """Localize the most likely leak locations in the pipe network.
    在管网中定位最可能的泄漏位置。

    Ranks pipes by the anomaly scores of their connected nodes and
    returns the *top_k* most suspicious pipe segments.

    Args:
        graph_data: Dict-graph from ``build_network_graph``.
                    由 ``build_network_graph`` 产生的字典图。
        anomaly_scores: Per-node anomaly scores from ``detect_leak``,
                        mapping node_id to float score.
                        由 ``detect_leak`` 产生的逐节点异常分数映射。
        top_k: Number of top suspects to return / 返回的最可疑管段数量

    Returns:
        Dict with suspects list (pipe_id, confidence, attention_weight,
        connected_nodes) and count.
        包含嫌疑管段列表和数量的字典。
    """
    if not isinstance(graph_data, dict):
        raise ValueError("graph_data must be a dict")
    if not isinstance(anomaly_scores, dict):
        raise ValueError("anomaly_scores must be a dict mapping node_id to float")
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}")

    from core.detection import localize_leak as _localize_leak

    suspects = _localize_leak(
        graph_data=graph_data,
        anomaly_scores=anomaly_scores,
        top_k=top_k,
    )

    return {
        "suspects": suspects,
        "n_suspects": len(suspects),
    }


@mcp.tool()
def fuse_leak_evidence(
    acoustic_events: list[dict],
    hydraulic_suspects: list[dict],
) -> dict:
    """Fuse acoustic sensor events with hydraulic anomaly suspects.
    将声学传感器事件与水力异常嫌疑管段融合。

    Combines two independent evidence streams using a Bayesian-style
    update to produce high-confidence leak localization results.

    Args:
        acoustic_events: List of acoustic event dicts, each with:
            - sensor_id: Sensor identifier / 传感器标识
            - timestamp: Event timestamp in seconds / 事件时间戳
            - amplitude_db: Signal amplitude in dB / 信号幅值
            - frequency_hz: Dominant frequency in Hz / 主频率
            - pipe_segment: Associated pipe segment ID / 关联管段标识
            声学事件字典列表。
        hydraulic_suspects: List of suspect dicts from ``localize_leak``,
                            each with 'pipe_id' and 'confidence'.
                            由 ``localize_leak`` 产生的嫌疑管段字典列表。

    Returns:
        Dict with fused_results list (pipe_id, combined_confidence,
        evidence) and count.
        包含融合结果列表和数量的字典。
    """
    if not isinstance(acoustic_events, list):
        raise ValueError("acoustic_events must be a list of dicts")
    if not isinstance(hydraulic_suspects, list):
        raise ValueError("hydraulic_suspects must be a list of dicts")

    for i, evt in enumerate(acoustic_events):
        if not isinstance(evt, dict):
            raise ValueError(f"acoustic_events[{i}] must be a dict, got {type(evt)}")
        if "pipe_segment" not in evt:
            raise ValueError(
                f"acoustic_events[{i}] must have 'pipe_segment' key, got {evt!r}"
            )

    for j, suspect in enumerate(hydraulic_suspects):
        if not isinstance(suspect, dict):
            raise ValueError(
                f"hydraulic_suspects[{j}] must be a dict, got {type(suspect)}"
            )
        if "pipe_id" not in suspect or "confidence" not in suspect:
            raise ValueError(
                f"hydraulic_suspects[{j}] must have 'pipe_id' and 'confidence' keys, "
                f"got {suspect!r}"
            )

    from core.detection import AcousticEvent, fuse_acoustic_hydraulic

    # Convert raw dicts to AcousticEvent dataclass instances
    events = []
    for evt in acoustic_events:
        events.append(
            AcousticEvent(
                sensor_id=str(evt.get("sensor_id", "")),
                timestamp=float(evt.get("timestamp", 0.0)),
                amplitude_db=float(evt.get("amplitude_db", 0.0)),
                frequency_hz=float(evt.get("frequency_hz", 0.0)),
                pipe_segment=str(evt["pipe_segment"]),
            )
        )

    fused = fuse_acoustic_hydraulic(events, hydraulic_suspects)

    return {
        "fused_results": fused,
        "n_results": len(fused),
    }


if __name__ == "__main__":
    mcp.run()
