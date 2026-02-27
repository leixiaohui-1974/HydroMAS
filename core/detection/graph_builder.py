"""Graph builder — convert pipe network topology to graph representations.
图构建器 — 将管网拓扑转换为图数据表示。

Supports both pure-Python dict graphs and PyG (torch_geometric) Data objects.
支持纯 Python 字典图和 PyG（torch_geometric）Data 对象。
"""

from __future__ import annotations


def network_to_dict_graph(
    nodes: list[dict],
    edges: list[dict],
) -> dict:
    """Convert network topology to a pure-Python dict graph.
    将管网拓扑转换为纯 Python 字典图。

    No external dependencies required.

    Args:
        nodes: List of node dicts, each with 'id' and 'features' keys.
               features = [flow, pressure, residual].
               节点列表，每个包含 'id' 和 'features' 键。
        edges: List of edge dicts, each with 'source', 'target', and 'features' keys.
               features = [length, diameter, material_code].
               边列表，每个包含 'source'、'target' 和 'features' 键。

    Returns:
        Dict with 'nodes', 'edges', and 'adjacency'.
        包含 'nodes'、'edges' 和 'adjacency' 的字典。
    """
    node_map: dict[str, dict] = {}
    for n in nodes:
        node_id = str(n["id"])
        node_map[node_id] = {"features": list(n["features"])}

    edge_list: list[dict] = []
    adjacency: dict[str, list[str]] = {str(n["id"]): [] for n in nodes}

    for e in edges:
        src = str(e["source"])
        tgt = str(e["target"])
        edge_list.append({
            "source": src,
            "target": tgt,
            "features": list(e["features"]),
        })
        if src in adjacency:
            adjacency[src].append(tgt)
        else:
            adjacency[src] = [tgt]

    return {
        "nodes": node_map,
        "edges": edge_list,
        "adjacency": adjacency,
    }


def network_to_pyg_graph(
    nodes: list[dict],
    edges: list[dict],
):
    """Convert network topology to a torch_geometric Data object.
    将管网拓扑转换为 torch_geometric Data 对象。

    Requires torch and torch_geometric. Raises ValueError if not installed.

    Args:
        nodes: List of node dicts, each with 'id' and 'features' keys.
               features = [flow, pressure, residual].
               节点列表，每个包含 'id' 和 'features' 键。
        edges: List of edge dicts, each with 'source', 'target', and 'features' keys.
               features = [length, diameter, material_code].
               边列表，每个包含 'source'、'target' 和 'features' 键。

    Returns:
        torch_geometric.data.Data object with x, edge_index, edge_attr, and node_ids.
        包含 x、edge_index、edge_attr 和 node_ids 的 Data 对象。
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        raise ValueError(
            "torch not installed. Install with: pip install torch"
        )

    try:
        from torch_geometric.data import Data  # noqa: F401
    except ImportError:
        raise ValueError(
            "torch_geometric not installed. Install with: pip install torch_geometric"
        )

    # Build node id -> index mapping
    node_ids: list[str] = [str(n["id"]) for n in nodes]
    id_to_idx: dict[str, int] = {nid: i for i, nid in enumerate(node_ids)}

    # Node feature matrix
    x = torch.tensor(
        [n["features"] for n in nodes],
        dtype=torch.float,
    )

    # Edge index (COO format) and edge attributes
    src_indices: list[int] = []
    tgt_indices: list[int] = []
    edge_features: list[list[float]] = []

    for e in edges:
        src = str(e["source"])
        tgt = str(e["target"])
        src_indices.append(id_to_idx[src])
        tgt_indices.append(id_to_idx[tgt])
        edge_features.append(list(e["features"]))

    edge_index = torch.tensor(
        [src_indices, tgt_indices],
        dtype=torch.long,
    )
    edge_attr = torch.tensor(edge_features, dtype=torch.float)

    return Data(
        x=x,
        edge_index=edge_index,
        edge_attr=edge_attr,
        node_ids=node_ids,
    )
