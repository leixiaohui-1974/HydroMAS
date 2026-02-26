"""MCP Server: System identification tools.
MCP 服务器：系统辨识工具。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Identification")


@mcp.tool()
def identify_parameters(
    observed_h: list[float],
    observed_q_out: list[float],
    model_type: str = "nonlinear",
    initial_guess: dict | None = None,
    arx_config: dict | None = None,
) -> dict:
    """Identify tank model parameters from observed data.
    从观测数据辨识水箱模型参数。

    Args:
        observed_h: Observed water level series (m) / 观测水位序列
        observed_q_out: Observed outflow series (m³/s) / 观测出流序列
        model_type: "nonlinear" (least squares) or "ARX" / 模型类型
        initial_guess: Initial parameter guess for nonlinear / 非线性模型初始猜测
        arx_config: ARX model config {na, nb, nk, u} / ARX 模型配置

    Returns:
        Dict with identified parameters and fit metrics.
    """
    if model_type.upper() == "ARX":
        from core.identification.arx_model import identify_arx
        cfg = arx_config or {}
        return identify_arx(
            y=observed_h,
            u=cfg.get("u", observed_q_out),
            na=cfg.get("na", 2),
            nb=cfg.get("nb", 2),
            nk=cfg.get("nk", 1),
        )
    else:
        from core.identification.least_squares import identify_tank_params
        return identify_tank_params(
            observed_h=observed_h,
            observed_q_out=observed_q_out,
            initial_guess=initial_guess,
        )


if __name__ == "__main__":
    mcp.run()
