"""Residual analysis — anomaly detection and classification for water balance.
残差分析 — 水平衡异常检测与分类。

Provides rolling residual computation, threshold-based anomaly detection,
and heuristic classification of anomaly root causes (leak, meter error,
process change).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity thresholds (relative error boundaries)
# ---------------------------------------------------------------------------

_SEVERITY_HIGH: float = 0.10
_SEVERITY_MEDIUM: float = 0.05


def detect_anomaly(
    residuals: dict[str, float],
    threshold: float = 0.03,
) -> list[dict]:
    """Detect anomalous nodes whose residual exceeds a threshold.
    检测残差超过阈值的异常节点。

    Each node's residual is compared against *threshold* in absolute terms.
    Severity is assigned based on the magnitude of the relative error:

    * ``"high"``   — relative error >= 10 %
    * ``"medium"`` — relative error >= 5 %
    * ``"low"``    — relative error >= *threshold*

    Args:
        residuals: Mapping of node_id to residual value (m³/s) /
                   节点 ID 到残差值的映射
        threshold: Minimum absolute residual to flag as anomaly /
                   标记异常的最小绝对残差阈值

    Returns:
        List of dicts, each with keys: node_id, residual,
        relative_error, severity.
        字典列表，每项包含 node_id、residual、relative_error、severity。
    """
    if threshold < 0:
        raise ValueError(f"threshold must be non-negative, got {threshold}")

    anomalies: list[dict] = []
    for node_id, residual in residuals.items():
        abs_residual = abs(residual)
        if abs_residual < threshold:
            continue

        # Relative error: use 1.0 as denominator floor to avoid division
        # by very small residuals amplifying the ratio.
        relative_error = abs_residual  # dimensionless when flows ≈ 1 m³/s

        if relative_error >= _SEVERITY_HIGH:
            severity = "high"
        elif relative_error >= _SEVERITY_MEDIUM:
            severity = "medium"
        else:
            severity = "low"

        anomalies.append({
            "node_id": node_id,
            "residual": residual,
            "relative_error": relative_error,
            "severity": severity,
        })

    # Sort by descending absolute residual for convenience
    anomalies.sort(key=lambda a: abs(a["residual"]), reverse=True)
    return anomalies


# ---------------------------------------------------------------------------
# Rolling residual
# ---------------------------------------------------------------------------

def calc_rolling_residual(
    time_series: list[dict],
    window: int = 12,
) -> dict[str, list[float]]:
    """Calculate rolling (moving-average) residual per node over time windows.
    按时间窗口计算每个节点的滚动残差。

    Each element of *time_series* is a dict mapping node IDs to residual
    values at that time step.  The function computes a simple moving average
    of the residuals using the given *window* size.

    Args:
        time_series: List of dicts ``{node_id: residual_value}`` ordered
                     chronologically / 按时间排序的残差字典列表
        window: Rolling window size (number of time steps) / 滚动窗口大小

    Returns:
        Dict mapping each node_id to a list of rolling-average residuals.
        Length of each list equals ``len(time_series) - window + 1``.
        字典，节点 ID 到滚动平均残差列表的映射。
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")
    if not time_series:
        return {}

    # Collect all node IDs that appear at least once
    all_node_ids: set[str] = set()
    for step in time_series:
        all_node_ids.update(step.keys())

    n_steps = len(time_series)
    if window > n_steps:
        logger.warning(
            "window (%d) > time_series length (%d); returning empty rolling residuals",
            window,
            n_steps,
        )
        return {nid: [] for nid in all_node_ids}

    result: dict[str, list[float]] = {nid: [] for nid in all_node_ids}

    for nid in all_node_ids:
        # Build a full vector (missing steps default to 0.0)
        values = [step.get(nid, 0.0) for step in time_series]

        # Compute rolling average using a running sum for efficiency
        running_sum = sum(values[:window])
        result[nid].append(running_sum / window)

        for i in range(window, n_steps):
            running_sum += values[i] - values[i - window]
            result[nid].append(running_sum / window)

    return result


# ---------------------------------------------------------------------------
# Anomaly classification
# ---------------------------------------------------------------------------

def classify_anomaly(anomalies: list[dict]) -> dict:
    """Classify anomalies by probable root cause.
    按可能的根因对异常进行分类。

    Heuristic rules:

    * **leak** — persistent negative residual (Q_in < Q_out + losses),
      indicates water leaving the system unaccounted.
    * **meter_error** — residual is positive *or* severity is ``"low"``,
      suggesting instrumentation drift rather than physical loss.
    * **process_change** — high-severity anomalies that could stem from
      operational regime changes (e.g., new demand pattern).

    Args:
        anomalies: List of anomaly dicts as returned by
                   :func:`detect_anomaly` / 由 detect_anomaly 返回的异常列表

    Returns:
        Dict with keys ``leak``, ``meter_error``, ``process_change``, each
        mapping to a list of anomaly dicts belonging to that category.
        字典，键为 leak / meter_error / process_change，值为对应异常列表。
    """
    classified: dict[str, list[dict]] = {
        "leak": [],
        "meter_error": [],
        "process_change": [],
    }

    for anomaly in anomalies:
        residual = anomaly.get("residual", 0.0)
        severity = anomaly.get("severity", "low")

        if severity == "high":
            # High-severity: could be process change or major leak
            if residual < 0:
                classified["leak"].append(anomaly)
            else:
                classified["process_change"].append(anomaly)
        elif residual < 0 and severity == "medium":
            # Medium negative residual suggests a leak
            classified["leak"].append(anomaly)
        else:
            # Low severity or positive residual — likely meter drift
            classified["meter_error"].append(anomaly)

    return classified
