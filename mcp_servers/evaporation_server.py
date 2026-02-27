"""MCP Server: Evaporation prediction tools.
MCP 服务器：蒸发预测工具。

Exposes cooling tower (Merkel), calcination, red mud, and total
evaporation loss prediction as MCP tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Evaporation")


@mcp.tool()
def predict_evaporation(
    tower_params: dict,
    weather: dict,
) -> dict:
    """Predict cooling tower evaporation using the Merkel energy-balance model.
    基于 Merkel 能量平衡模型预测冷却塔蒸发量。

    Args:
        tower_params: Cooling tower parameters / 冷却塔参数:
            - water_flow_m3h: Circulation water flow (m³/h) / 循环水流量
            - t_in: Inlet water temperature (°C) / 进水温度
            - t_out: Outlet water temperature (°C) / 出水温度
            - n_cells: Number of cells (optional) / 冷却塔单元数
            - fan_power_kw: Fan power per cell kW (optional) / 风机功率
        weather: Weather conditions / 气象条件:
            - t_db: Dry-bulb temperature (°C) / 干球温度
            - t_wb: Wet-bulb temperature (°C) / 湿球温度
            - humidity: Relative humidity (0-1) / 相对湿度
            - wind_speed: Wind speed (m/s) / 风速

    Returns:
        Dict with evap_rate_m3h, evap_daily_m3, evap_ratio, and details.
        包含蒸发速率、日蒸发量、蒸发比和详细分解的字典。
    """
    if not isinstance(tower_params, dict):
        raise ValueError("tower_params must be a dict")
    if not isinstance(weather, dict):
        raise ValueError("weather must be a dict")
    if tower_params.get("water_flow_m3h", 0) <= 0:
        raise ValueError("tower_params.water_flow_m3h must be positive")

    from core.evaporation import CoolingTowerParams, calc_evaporation_merkel

    params = CoolingTowerParams(
        water_flow_m3h=float(tower_params.get("water_flow_m3h", 500.0)),
        t_in=float(tower_params.get("t_in", 42.0)),
        t_out=float(tower_params.get("t_out", 32.0)),
        n_cells=int(tower_params.get("n_cells", 4)),
        fan_power_kw=float(tower_params.get("fan_power_kw", 55.0)),
    )

    return calc_evaporation_merkel(params, weather)


@mcp.tool()
def predict_calcination_evap(
    slurry_flow: float,
    moisture: float,
    temp: float,
) -> dict:
    """Predict evaporation from calcination process (rotary kiln / flash calciner).
    预测焙烧过程（回转窑/闪速焙烧）的蒸发量。

    Args:
        slurry_flow: Wet slurry volumetric flow (m³/h) / 湿浆料体积流量
        moisture: Water mass fraction in slurry (0-1) / 浆料含水率
        temp: Calcination temperature (°C) / 焙烧温度

    Returns:
        Dict with evap_rate_m3h, evap_daily_m3, energy_consumption_kwh,
        and details.
        包含蒸发速率、日蒸发量、能耗和详细分解的字典。
    """
    if slurry_flow <= 0:
        raise ValueError(f"slurry_flow must be positive, got {slurry_flow}")
    if moisture <= 0 or moisture >= 1:
        raise ValueError(f"moisture must be in (0, 1), got {moisture}")
    if temp <= 0:
        raise ValueError(f"temp must be positive, got {temp}")

    from core.evaporation import CalcinationParams, calc_calcination_evap

    params = CalcinationParams(
        slurry_flow_m3h=slurry_flow,
        moisture_content=moisture,
        calcination_temp=temp,
    )

    return calc_calcination_evap(params)


@mcp.tool()
def predict_red_mud_water(
    mud_mass: float,
    moisture_ratio: float,
) -> dict:
    """Predict water carried out by stacked red mud.
    预测赤泥堆存带出的水量。

    Args:
        mud_mass: Dry red mud mass (t/d) / 干赤泥质量（吨/日）
        moisture_ratio: Moisture ratio — water mass / wet mud mass (0-1) / 含水率

    Returns:
        Dict with water_carry_m3d, water_carry_m3h, and details.
        包含日带水量、小时带水量和详细信息的字典。
    """
    if mud_mass <= 0:
        raise ValueError(f"mud_mass must be positive, got {mud_mass}")
    if moisture_ratio <= 0 or moisture_ratio >= 1:
        raise ValueError(
            f"moisture_ratio must be in (0, 1), got {moisture_ratio}"
        )

    from core.evaporation import RedMudParams, calc_red_mud_water

    params = RedMudParams(
        mud_dry_mass_td=mud_mass,
        moisture_ratio=moisture_ratio,
    )

    return calc_red_mud_water(params)


@mcp.tool()
def predict_total_evap_loss(
    tower_params: dict,
    weather: dict,
    calc_params: dict,
    mud_params: dict,
) -> dict:
    """Predict total evaporation loss from all three sources combined.
    预测三种来源蒸发损耗的总和。

    Sums evaporation from cooling tower (Merkel), calcination, and
    red mud carry-out to give a plant-wide daily water loss estimate.

    Args:
        tower_params: Cooling tower parameters / 冷却塔参数:
            - water_flow_m3h, t_in, t_out, n_cells, fan_power_kw
        weather: Weather conditions / 气象条件:
            - t_db, t_wb, humidity, wind_speed
        calc_params: Calcination parameters / 焙烧参数:
            - slurry_flow: m³/h, moisture: 0-1, temp: °C
        mud_params: Red mud parameters / 赤泥参数:
            - mud_mass: t/d, moisture_ratio: 0-1

    Returns:
        Dict with total_daily_m3, total_hourly_m3, and per-source breakdown.
        包含日总蒸发量、小时总蒸发量和分项明细的字典。
    """
    if not isinstance(tower_params, dict):
        raise ValueError("tower_params must be a dict")
    if not isinstance(weather, dict):
        raise ValueError("weather must be a dict")
    if not isinstance(calc_params, dict):
        raise ValueError("calc_params must be a dict")
    if not isinstance(mud_params, dict):
        raise ValueError("mud_params must be a dict")

    from core.evaporation import (
        CoolingTowerParams,
        calc_evaporation_merkel,
        CalcinationParams,
        calc_calcination_evap,
        RedMudParams,
        calc_red_mud_water,
    )

    # Cooling tower evaporation
    ct_params = CoolingTowerParams(
        water_flow_m3h=float(tower_params.get("water_flow_m3h", 500.0)),
        t_in=float(tower_params.get("t_in", 42.0)),
        t_out=float(tower_params.get("t_out", 32.0)),
        n_cells=int(tower_params.get("n_cells", 4)),
        fan_power_kw=float(tower_params.get("fan_power_kw", 55.0)),
    )
    tower_result = calc_evaporation_merkel(ct_params, weather)

    # Calcination evaporation
    ca_params = CalcinationParams(
        slurry_flow_m3h=float(calc_params.get("slurry_flow", 50.0)),
        moisture_content=float(calc_params.get("moisture", 0.45)),
        calcination_temp=float(calc_params.get("temp", 1050.0)),
    )
    calc_result = calc_calcination_evap(ca_params)

    # Red mud water carry-out
    rm_params = RedMudParams(
        mud_dry_mass_td=float(mud_params.get("mud_mass", 500.0)),
        moisture_ratio=float(mud_params.get("moisture_ratio", 0.55)),
    )
    mud_result = calc_red_mud_water(rm_params)

    # Sum totals
    tower_daily = tower_result["evap_daily_m3"]
    calc_daily = calc_result["evap_daily_m3"]
    mud_daily = mud_result["water_carry_m3d"]
    total_daily = tower_daily + calc_daily + mud_daily

    tower_hourly = tower_result["evap_rate_m3h"]
    calc_hourly = calc_result["evap_rate_m3h"]
    mud_hourly = mud_result["water_carry_m3h"]
    total_hourly = tower_hourly + calc_hourly + mud_hourly

    return {
        "total_daily_m3": total_daily,
        "total_hourly_m3": total_hourly,
        "breakdown": {
            "cooling_tower": {
                "daily_m3": tower_daily,
                "hourly_m3": tower_hourly,
            },
            "calcination": {
                "daily_m3": calc_daily,
                "hourly_m3": calc_hourly,
            },
            "red_mud": {
                "daily_m3": mud_daily,
                "hourly_m3": mud_hourly,
            },
        },
        "details": {
            "cooling_tower": tower_result,
            "calcination": calc_result,
            "red_mud": mud_result,
        },
    }


if __name__ == "__main__":
    mcp.run()
