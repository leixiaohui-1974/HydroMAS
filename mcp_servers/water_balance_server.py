"""MCP Server: Water balance calculation tools.
MCP 服务器：水平衡计算工具。

Exposes node-level balance, full plant balance, and anomaly detection
as MCP tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-WaterBalance")


@mcp.tool()
def calc_node_balance(
    node_id: str,
    node_type: str,
    q_in: float,
    q_out: float,
    q_loss: float = 0.0,
    q_evap: float = 0.0,
    volume: float = 0.0,
    capacity: float = 0.0,
    dv_dt: float = 0.0,
) -> dict:
    """Create a BalanceNode, validate it, and calculate the residual.
    创建平衡节点、验证并计算残差。

    Args:
        node_id: Unique node identifier / 节点唯一标识
        node_type: Node type (intake/pool/workshop/reuse/wastewater) / 节点类型
        q_in: Inflow rate (m³/s) / 入流量
        q_out: Outflow rate (m³/s) / 出流量
        q_loss: Loss rate (m³/s) / 漏损量
        q_evap: Evaporation rate (m³/s) / 蒸发损失
        volume: Current volume (m³) / 当前蓄水量
        capacity: Maximum capacity (m³) / 最大容量
        dv_dt: Rate of volume change (m³/s) / 蓄水量变化率

    Returns:
        Dict with node_id, node_type, residual, and is_balanced flag.
        包含 node_id、node_type、residual 和 is_balanced 标志的字典。
    """
    if not node_id:
        raise ValueError("node_id must be a non-empty string")
    if q_in < 0:
        raise ValueError(f"q_in must be non-negative, got {q_in}")
    if q_out < 0:
        raise ValueError(f"q_out must be non-negative, got {q_out}")

    from core.water_balance import BalanceNode, calc_node_residual

    node = BalanceNode(
        node_id=node_id,
        node_type=node_type,
        q_in=q_in,
        q_out=q_out,
        q_loss=q_loss,
        q_evap=q_evap,
        volume=volume,
        capacity=capacity,
    )
    node.validate()

    residual = calc_node_residual(node, dv_dt=dv_dt)

    return {
        "node_id": node_id,
        "node_type": node_type,
        "residual": residual,
        "is_balanced": abs(residual) < 0.03,
    }


@mcp.tool()
def calc_full_plant_balance(
    nodes_data: list[dict],
    edges_data: list[list[str]],
) -> dict:
    """Build a plant-wide balance graph and calculate full balance.
    构建全厂水平衡图并计算整体水平衡。

    Args:
        nodes_data: List of node dicts, each with keys:
                    node_id, node_type, q_in, q_out, and optionally
                    q_loss, q_evap, volume, capacity.
                    节点字典列表，每个包含 node_id、node_type、q_in、q_out，
                    可选 q_loss、q_evap、volume、capacity。
        edges_data: List of [source_id, destination_id] pairs / 边列表

    Returns:
        Dict with node_residuals, total_intake, total_consumption,
        total_loss, total_evap, reuse_rate, balance_error.
        包含节点残差、总取水量、总消耗量、总漏损、总蒸发、回用率、
        平衡误差的字典。
    """
    if not nodes_data:
        raise ValueError("nodes_data list cannot be empty")
    if not isinstance(edges_data, list):
        raise ValueError("edges_data must be a list of [source, target] pairs")

    from core.water_balance import BalanceNode, build_balance_graph, calc_full_balance

    # Build BalanceNode instances from dicts
    nodes = []
    for i, nd in enumerate(nodes_data):
        if "node_id" not in nd or "node_type" not in nd:
            raise ValueError(
                f"nodes_data[{i}] must have 'node_id' and 'node_type' keys, got {nd!r}"
            )
        node = BalanceNode(
            node_id=nd["node_id"],
            node_type=nd["node_type"],
            q_in=float(nd.get("q_in", 0.0)),
            q_out=float(nd.get("q_out", 0.0)),
            q_loss=float(nd.get("q_loss", 0.0)),
            q_evap=float(nd.get("q_evap", 0.0)),
            volume=float(nd.get("volume", 0.0)),
            capacity=float(nd.get("capacity", 0.0)),
        )
        node.validate()
        nodes.append(node)

    # Convert edge pairs
    edges = []
    for j, edge in enumerate(edges_data):
        if not isinstance(edge, (list, tuple)) or len(edge) < 2:
            raise ValueError(
                f"edges_data[{j}] must be [source, target], got {edge!r}"
            )
        edges.append((str(edge[0]), str(edge[1])))

    graph = build_balance_graph(nodes, edges)
    return calc_full_balance(graph)


@mcp.tool()
def detect_balance_anomaly(
    residuals: dict,
    threshold: float = 0.03,
) -> dict:
    """Detect anomalous nodes whose residual exceeds a threshold.
    检测残差超过阈值的异常节点。

    Args:
        residuals: Mapping of node_id to residual value (m³/s) /
                   节点 ID 到残差值的映射
        threshold: Minimum absolute residual to flag as anomaly /
                   标记异常的最小绝对残差阈值

    Returns:
        Dict with anomalies list and classification by root cause
        (leak, meter_error, process_change).
        包含异常列表和按根因分类（漏损、仪表误差、工况变化）的字典。
    """
    if not isinstance(residuals, dict):
        raise ValueError("residuals must be a dict mapping node_id to float")
    if threshold < 0:
        raise ValueError(f"threshold must be non-negative, got {threshold}")

    from core.water_balance import classify_anomaly, detect_anomaly

    anomalies = detect_anomaly(residuals, threshold=threshold)
    classification = classify_anomaly(anomalies)

    return {
        "anomalies": anomalies,
        "classification": classification,
        "n_anomalies": len(anomalies),
    }


if __name__ == "__main__":
    mcp.run()
