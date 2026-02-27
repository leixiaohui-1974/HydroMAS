"""MCP Server: Performance evaluation tools.
MCP 服务器：性能评价工具。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Evaluation")


@mcp.tool()
def evaluate_performance(
    observed: list[float],
    predicted: list[float],
    metrics: list[str] | None = None,
    time_series: list[float] | None = None,
    setpoint: float | None = None,
) -> dict:
    """Evaluate prediction/control performance using multiple metrics.
    使用多个指标评估预测/控制性能。

    Args:
        observed: Observed/reference values / 观测/参考值
        predicted: Predicted/simulated values / 预测/仿真值
        metrics: Metrics to compute / 需要计算的指标
            Options: "RMSE", "MAE", "NSE", "MAPE", "settling_time", "overshoot", "steady_state_error"
        time_series: Time values (for settling_time) / 时间序列
        setpoint: Target value (for control metrics) / 目标值

    Returns:
        Dict of metric name to value.
    """
    if not observed or not predicted:
        raise ValueError("observed and predicted lists cannot be empty")
    if len(observed) != len(predicted):
        raise ValueError(
            f"observed and predicted must have same length, "
            f"got {len(observed)} and {len(predicted)}"
        )

    from core.evaluation.metrics import evaluate_performance as _eval
    return _eval(observed, predicted, metrics_list=metrics, time_series=time_series, setpoint=setpoint)


@mcp.tool()
def assess_wnal(
    system_capabilities: dict[str, float],
) -> dict:
    """Assess WNAL (Water Network Autonomy Level) of the system.
    评估系统的水网自主运行等级（WNAL）。

    Args:
        system_capabilities: Capability scores (0-100) for each dimension:
            sensing, communication, modeling, prediction, control,
            odd_monitoring, decision_support / 各能力维度得分

    Returns:
        Dict with WNAL level, score, gaps, and recommendations.
    """
    from core.evaluation.wnal_assessor import assess_wnal as _assess
    return _assess(system_capabilities)


if __name__ == "__main__":
    mcp.run()
