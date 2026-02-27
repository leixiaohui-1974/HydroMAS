"""GNN-based leak detection — GAT model construction and anomaly scoring.
基于 GNN 的泄漏检测 — GAT 模型构建与异常评分。

Uses Graph Attention Networks for node-level anomaly detection on
pipe network snapshots.  Falls back to statistical detection when
torch / torch_geometric are not available.
当 torch / torch_geometric 不可用时退化为统计检测。
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def build_gat_model(
    n_node_features: int = 3,
    n_edge_features: int = 3,
    hidden_dim: int = 64,
    n_heads: int = 4,
) -> dict:
    """Build a GAT model configuration (and optionally a torch model).
    构建 GAT 模型配置（可选返回 torch 模型）。

    If torch and torch_geometric are available, returns a dict containing
    both the config and the instantiated model.  Otherwise, returns the
    config dict only.

    Args:
        n_node_features: Number of node features (default 3: flow, pressure, residual).
                         节点特征数（默认 3：流量、压力、残差）
        n_edge_features: Number of edge features (default 3: length, diameter, material_code).
                         边特征数（默认 3：长度、管径、材质码）
        hidden_dim: Hidden layer dimension / 隐藏层维度
        n_heads: Number of attention heads / 注意力头数

    Returns:
        Dict with model config and, when available, the torch model.
        包含模型配置的字典，可用时附带 torch 模型。
    """
    config: dict = {
        "architecture": "GATv2",
        "n_node_features": n_node_features,
        "n_edge_features": n_edge_features,
        "hidden_dim": hidden_dim,
        "n_heads": n_heads,
        "output_dim": 1,
        "layers": [
            {"type": "GATv2Conv", "in": n_node_features, "out": hidden_dim, "heads": n_heads},
            {"type": "GATv2Conv", "in": hidden_dim * n_heads, "out": hidden_dim, "heads": 1},
            {"type": "Linear", "in": hidden_dim, "out": 1},
        ],
    }

    try:
        import torch  # noqa: F401
        from torch_geometric.nn import GATv2Conv  # noqa: F401
    except ImportError:
        config["model"] = None
        config["note"] = "torch/torch_geometric not installed; config only"
        return config

    # When torch is available, build an actual model
    import torch.nn as nn

    class _GATLeakDetector(nn.Module):
        """Lightweight GAT for per-node anomaly scoring."""

        def __init__(self) -> None:
            super().__init__()
            self.conv1 = GATv2Conv(
                n_node_features, hidden_dim, heads=n_heads, edge_dim=n_edge_features,
            )
            self.conv2 = GATv2Conv(
                hidden_dim * n_heads, hidden_dim, heads=1, edge_dim=n_edge_features,
            )
            self.linear = nn.Linear(hidden_dim, 1)
            self.activation = nn.ELU()

        def forward(self, x, edge_index, edge_attr=None):  # type: ignore[override]
            h = self.activation(self.conv1(x, edge_index, edge_attr=edge_attr))
            h = self.activation(self.conv2(h, edge_index, edge_attr=edge_attr))
            return torch.sigmoid(self.linear(h))

    model = _GATLeakDetector()
    config["model"] = model
    return config


# ---- Statistical fallback helpers ------------------------------------------------


def _statistical_anomaly_scores(graph_data: dict) -> dict[str, float]:
    """Compute z-score-based anomaly scores from node features (no torch).
    基于 z-score 从节点特征计算异常分数（无需 torch）。
    """
    nodes = graph_data.get("nodes", {})
    if not nodes:
        return {}

    # Gather all feature vectors
    all_features: list[list[float]] = [
        n["features"] for n in nodes.values()
    ]
    n_feat = len(all_features[0])

    # Per-feature mean and std
    means = [0.0] * n_feat
    for feat in all_features:
        for j in range(n_feat):
            means[j] += feat[j]
    n_nodes = len(all_features)
    means = [m / n_nodes for m in means]

    stds = [0.0] * n_feat
    for feat in all_features:
        for j in range(n_feat):
            stds[j] += (feat[j] - means[j]) ** 2
    stds = [math.sqrt(s / max(n_nodes - 1, 1)) for s in stds]

    # Anomaly score = mean absolute z-score across features, mapped to [0, 1]
    scores: dict[str, float] = {}
    for node_id, node_data in nodes.items():
        z_total = 0.0
        for j in range(n_feat):
            if stds[j] > 1e-12:
                z_total += abs((node_data["features"][j] - means[j]) / stds[j])
            else:
                z_total += 0.0
        mean_z = z_total / n_feat
        # Sigmoid-like mapping to [0, 1]
        score = 1.0 / (1.0 + math.exp(-mean_z + 2.0))
        scores[node_id] = round(score, 6)

    return scores


# ---- Public API ------------------------------------------------------------------


def detect_leak(
    graph_data: dict,
    model_path: str | None = None,
    threshold: float = 0.95,
) -> dict:
    """Run leak detection on a graph snapshot.
    在图快照上执行泄漏检测。

    When torch is available and *model_path* is provided, runs the GNN
    model.  Otherwise, falls back to statistical anomaly detection on
    node features.

    Args:
        graph_data: Dict-graph from ``network_to_dict_graph``.
                    由 ``network_to_dict_graph`` 产生的字典图。
        model_path: Optional path to a trained model checkpoint.
                    可选的训练模型检查点路径。
        threshold: Anomaly score threshold for leak flag / 泄漏标志的异常分数阈值

    Returns:
        Dict with leak_detected (bool), anomaly_scores ({node_id: score}),
        and max_score (float).
        包含 leak_detected、anomaly_scores 和 max_score 的字典。
    """
    use_gnn = False
    if model_path is not None:
        try:
            import torch  # noqa: F401
            use_gnn = True
        except ImportError:
            use_gnn = False

    if use_gnn:
        import torch
        from core.detection.graph_builder import network_to_pyg_graph

        # Rebuild nodes/edges lists from dict-graph
        nodes_list = [
            {"id": nid, "features": ndata["features"]}
            for nid, ndata in graph_data["nodes"].items()
        ]
        edges_list = graph_data["edges"]

        pyg_data = network_to_pyg_graph(nodes_list, edges_list)
        model_config = build_gat_model(
            n_node_features=pyg_data.x.shape[1],
            n_edge_features=pyg_data.edge_attr.shape[1] if pyg_data.edge_attr is not None else 0,
        )
        model = model_config["model"]
        model.load_state_dict(torch.load(model_path, map_location="cpu"))
        model.eval()

        with torch.no_grad():
            raw_scores = model(pyg_data.x, pyg_data.edge_index, pyg_data.edge_attr)
            raw_scores = raw_scores.squeeze(-1).tolist()

        anomaly_scores: dict[str, float] = {
            nid: round(s, 6)
            for nid, s in zip(pyg_data.node_ids, raw_scores)
        }
    else:
        anomaly_scores = _statistical_anomaly_scores(graph_data)

    max_score = max(anomaly_scores.values()) if anomaly_scores else 0.0
    leak_detected = max_score >= threshold

    return {
        "leak_detected": leak_detected,
        "anomaly_scores": anomaly_scores,
        "max_score": max_score,
    }


def localize_leak(
    graph_data: dict,
    anomaly_scores: dict[str, float],
    top_k: int = 3,
) -> list[dict]:
    """Localize the most likely leak locations in the network.
    在管网中定位最可能的泄漏位置。

    Ranks pipes by the anomaly scores of their connected nodes and
    returns the *top_k* most suspicious pipe segments.

    Args:
        graph_data: Dict-graph from ``network_to_dict_graph``.
                    由 ``network_to_dict_graph`` 产生的字典图。
        anomaly_scores: Per-node anomaly scores from ``detect_leak``.
                        由 ``detect_leak`` 产生的逐节点异常分数。
        top_k: Number of top suspects to return / 返回的最可疑管段数量

    Returns:
        List of dicts, each with pipe_id, confidence, attention_weight,
        and connected_nodes.
        字典列表，每个包含 pipe_id、confidence、attention_weight 和 connected_nodes。
    """
    edges = graph_data.get("edges", [])

    pipe_scores: list[dict] = []
    for idx, edge in enumerate(edges):
        src = str(edge["source"])
        tgt = str(edge["target"])
        src_score = anomaly_scores.get(src, 0.0)
        tgt_score = anomaly_scores.get(tgt, 0.0)

        # Confidence = max of endpoint scores; attention_weight = mean
        confidence = max(src_score, tgt_score)
        attention_weight = (src_score + tgt_score) / 2.0

        pipe_scores.append({
            "pipe_id": f"pipe_{src}_{tgt}",
            "confidence": round(confidence, 6),
            "attention_weight": round(attention_weight, 6),
            "connected_nodes": [src, tgt],
        })

    # Sort by confidence descending, then by attention_weight descending
    pipe_scores.sort(key=lambda p: (p["confidence"], p["attention_weight"]), reverse=True)

    return pipe_scores[:top_k]
