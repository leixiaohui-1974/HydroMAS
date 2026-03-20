"""MCP Server: ODD (Operational Design Domain) tools.
MCP 服务器：运行设计域（ODD）工具。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-ODD")


@mcp.tool()
def check_odd(
    current_state: dict[str, float],
    odd_config: dict | None = None,
    check_mode: str = "instant",
    forecast_series: list[dict[str, float]] | None = None,
    time_series: list[float] | None = None,
) -> dict:
    """Check system state against ODD boundaries.
    检查系统状态是否在 ODD 边界内。

    Modes:
        - "instant": Check current state only
        - "predictive": Check forecast series for future violations

    Args:
        current_state: Current state {dimension_name: value} / 当前状态
        odd_config: ODD specification dict (uses default tank ODD if None) / ODD 规格
        check_mode: "instant" or "predictive" / 检查模式
        forecast_series: Future states for predictive mode / 预测序列
        time_series: Time values for predictive mode / 时间序列

    Returns:
        Dict with zone classification, violations, and details.
    """
    from core.odd.odd_definition import ODDSpec, create_tank_odd
    from core.odd.odd_monitor import check_odd as _check
    from core.odd.odd_monitor import check_odd_series

    odd_spec = ODDSpec.from_dict(odd_config) if odd_config else create_tank_odd()

    if check_mode == "predictive" and forecast_series:
        return check_odd_series(forecast_series, time_series, odd_spec)
    else:
        return _check(current_state, odd_spec)


@mcp.tool()
def get_mrc_plan(
    violations: list[dict],
    current_state: dict,
) -> dict:
    """Generate MRC (Minimal Risk Condition) response plan for ODD violations.
    为 ODD 越界生成最小风险条件（MRC）响应计划。

    Args:
        violations: List of ODD violations / ODD 越界列表
        current_state: Current system state / 当前系统状态

    Returns:
        MRC plan with recommended actions and verification steps.
    """
    from core.odd.mrc_handler import generate_mrc_plan
    return generate_mrc_plan(violations, current_state)


@mcp.tool()
def check_alumina_odd(current_state: dict, odd_config: dict | None = None) -> dict:
    """Check alumina plant ODD with 12 dimensions. / 检查氧化铝厂12维ODD。"""
    import json
    from pathlib import Path
    if odd_config is None:
        config_path = Path(__file__).parent.parent / "data" / "alumina_odd_specs.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                odd_config = json.load(f)
        else:
            odd_config = {"dimensions": []}
    dimensions = odd_config.get("dimensions", [])
    violations = []
    zone = "normal"
    for dim in dimensions:
        name = dim["name"]
        if name not in current_state:
            continue
        value = current_state[name]
        min_val = dim["min_value"]
        max_val = dim["max_value"]
        margin = dim.get("warning_margin", 0.1)
        extended_min = min_val - (max_val - min_val) * margin
        extended_max = max_val + (max_val - min_val) * margin
        if value < min_val or value > max_val:
            if value < extended_min or value > extended_max:
                violations.append({
                    "dimension": name, "value": value,
                    "zone": "mrc", "bounds": [min_val, max_val],
                })
                zone = "mrc"
            else:
                violations.append({
                    "dimension": name, "value": value,
                    "zone": "extended",
                    "bounds": [min_val, max_val],
                })
                if zone != "mrc":
                    zone = "extended"
    n_checked = len(
        [d for d in dimensions if d["name"] in current_state]
    )
    return {
        "zone": zone,
        "violations": violations,
        "n_checked": n_checked,
        "n_violations": len(violations),
    }


if __name__ == "__main__":
    mcp.run()
