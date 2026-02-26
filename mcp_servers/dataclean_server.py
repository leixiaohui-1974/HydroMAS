"""MCP Server: Data cleaning tools for time series.
MCP 服务器：时序数据清洗工具。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-DataClean")


@mcp.tool()
def clean_timeseries(
    raw_data: list[float],
    methods: list[str] | None = None,
) -> dict:
    """Clean time series data using a pipeline of methods.
    使用方法管道清洗时序数据。

    Args:
        raw_data: Raw time series values / 原始时序数据
        methods: Cleaning methods to apply in order / 按序应用的清洗方法
            Options: "outlier_3sigma", "outlier_iqr", "interpolate_linear",
                     "interpolate_spline", "median_filter"

    Returns:
        Dict with cleaned data and processing steps.
    """
    from core.data_clean.interpolation import clean_timeseries as _clean
    return _clean(raw_data=raw_data, methods=methods)


@mcp.tool()
def detect_outliers(
    data: list[float],
    method: str = "3sigma",
    threshold: float = 3.0,
) -> dict:
    """Detect outliers in time series data.
    检测时序数据中的异常值。

    Args:
        data: Input time series / 输入时序
        method: Detection method ("3sigma", "iqr", "mad") / 检测方法
        threshold: Detection threshold / 检测阈值

    Returns:
        Dict with outlier indices and statistics.
    """
    from core.data_clean.outlier_detect import detect_3sigma, detect_iqr, detect_mad

    if method == "3sigma":
        return detect_3sigma(data, threshold=threshold)
    elif method == "iqr":
        return detect_iqr(data, factor=threshold)
    elif method == "mad":
        return detect_mad(data, threshold=threshold)
    else:
        raise ValueError(f"Unknown method: {method}. Use '3sigma', 'iqr', or 'mad'.")


if __name__ == "__main__":
    mcp.run()
