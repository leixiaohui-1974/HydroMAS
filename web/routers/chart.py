"""Chart API router — generate matplotlib charts from simulation data.
图表 API 路由 — 从仿真数据生成 matplotlib 过程线图。
"""

from __future__ import annotations

import asyncio
import io
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

# ── Font cache (avoid reloading TTF on every chart render) ──
_FONT_CACHE: dict = {}


def _get_font(bold: bool = False):
    """Get cached FontProperties for Chinese text rendering."""
    key = "bold" if bold else "regular"
    if key not in _FONT_CACHE:
        from matplotlib.font_manager import FontProperties
        if bold:
            _FONT_CACHE[key] = FontProperties(
                fname="/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc", size=14)
        else:
            _FONT_CACHE[key] = FontProperties(
                fname="/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc")
    return _FONT_CACHE[key]


class ChartRequest(BaseModel):
    """Request body for chart generation."""
    time: list[float]
    water_level: list[float]
    outflow: list[float] = []
    inflow: list[float] = []
    title: str = "水箱仿真结果"
    # Optional second tank for dual-tank display
    water_level_2: list[float] = []
    outflow_2: list[float] = []


class SimChartRequest(BaseModel):
    """Run simulation + generate chart in one call."""
    duration: float = 300.0
    dt: float = 1.0
    initial_h: float = 0.5
    q_in_profile: Optional[list[list[float]]] = None
    tank_params: Optional[dict] = None
    solver: str = "rk4"
    title: str = "水箱仿真结果"


def _render_chart(data: dict) -> bytes:
    """Render simulation data as a PNG chart using matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    font = _get_font(bold=False)
    font_title = _get_font(bold=True)

    time = data["time"]
    wl = data["water_level"]
    outflow = data.get("outflow", [])
    inflow = data.get("inflow", [])
    wl2 = data.get("water_level_2", [])
    outflow2 = data.get("outflow_2", [])
    title = data.get("title", "水箱仿真结果")

    has_dual = bool(wl2)
    n_plots = 2  # water level + flow rate

    fig, axes = plt.subplots(n_plots, 1, figsize=(10, 4 * n_plots), dpi=120)
    fig.suptitle(title, fontproperties=font_title, y=0.98)

    # --- Plot 1: Water Level ---
    ax1 = axes[0]
    ax1.plot(time, wl, "b-", linewidth=1.5, label="水箱1 水位")
    if has_dual:
        ax1.plot(time, wl2, "r--", linewidth=1.5, label="水箱2 水位")
    ax1.set_xlabel("时间 (s)", fontproperties=font)
    ax1.set_ylabel("水位 (m)", fontproperties=font)
    ax1.set_title("水位过程线", fontproperties=font)
    ax1.legend(prop=font, loc="best")
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(labelsize=9)

    # Add key value annotations
    ax1.annotate(f"h₀={wl[0]:.3f}m", xy=(time[0], wl[0]),
                 fontsize=9, color="blue", fontweight="bold")
    ax1.annotate(f"h_end={wl[-1]:.3f}m", xy=(time[-1], wl[-1]),
                 fontsize=9, color="blue", fontweight="bold",
                 ha="right")

    # --- Plot 2: Flow Rate ---
    ax2 = axes[1]
    if inflow:
        ax2.plot(time[:len(inflow)], inflow, "g-", linewidth=1.5, label="入流 Q_in")
    if outflow:
        ax2.plot(time[:len(outflow)], outflow, "b-", linewidth=1.5, label="水箱1 出流 Q_out")
    if outflow2:
        ax2.plot(time[:len(outflow2)], outflow2, "r--", linewidth=1.5, label="水箱2 出流")
    ax2.set_xlabel("时间 (s)", fontproperties=font)
    ax2.set_ylabel("流量 (m³/s)", fontproperties=font)
    ax2.set_title("流量过程线", fontproperties=font)
    ax2.legend(prop=font, loc="best")
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(labelsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


@router.post("/render")
async def render_chart(req: ChartRequest):
    """Generate a chart from provided simulation data.
    从仿真数据生成过程线图。返回 PNG 图片。
    """
    png = await asyncio.to_thread(_render_chart, req.model_dump())
    return StreamingResponse(io.BytesIO(png), media_type="image/png",
                             headers={"Content-Disposition": "inline; filename=simulation_chart.png"})


@router.post("/simulate-and-chart")
async def simulate_and_chart(req: SimChartRequest):
    """Run simulation then generate chart — one-step API.
    运行仿真 + 生成图表 — 一步到位。

    Returns JSON with simulation summary + base64 chart.
    """
    import base64

    from mcp_servers.simulation_server import simulate_tank

    result = await asyncio.to_thread(
        simulate_tank,
        duration=req.duration,
        dt=req.dt,
        initial_h=req.initial_h,
        q_in_profile=req.q_in_profile,
        tank_params=req.tank_params,
        solver=req.solver,
    )

    chart_data = {**result, "title": req.title}
    png = await asyncio.to_thread(_render_chart, chart_data)

    wl = result["water_level"]
    outflow = result.get("outflow", [])
    inflow = result.get("inflow", [])

    return {
        "summary": {
            "duration": req.duration,
            "dt": req.dt,
            "solver": req.solver,
            "initial_h": wl[0] if wl else req.initial_h,
            "final_h": wl[-1] if wl else None,
            "max_h": max(wl) if wl else None,
            "min_h": min(wl) if wl else None,
            "h_change": wl[-1] - wl[0] if wl else None,
            "inflow_start": inflow[0] if inflow else None,
            "inflow_end": inflow[-1] if inflow else None,
            "outflow_start": outflow[0] if outflow else None,
            "outflow_end": outflow[-1] if outflow else None,
            "steps": result.get("metadata", {}).get("steps", len(wl) - 1),
        },
        "chart_base64": base64.b64encode(png).decode("ascii"),
        "chart_size": len(png),
    }


class SchematicRequest(BaseModel):
    """Request body for tank schematic diagram."""
    tank_area_m2: float = 1.0
    discharge_coeff: float = 0.6
    outlet_area_m2: float = 0.01
    h_max_m: float = 2.0
    h_min_m: float = 0.0
    initial_h_m: float = 0.5
    q_in_m3s: float = 0.01
    title: str = "双容水箱系统示意图"


def _render_schematic(params: dict) -> bytes:
    """Render a conceptual tank schematic diagram."""
    import math
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    font = _get_font(bold=False)
    font_title = _get_font(bold=True)

    area = params.get("tank_area_m2", 1.0)
    h0 = params.get("initial_h_m", 0.5)
    h_max = params.get("h_max_m", 2.0)
    cd = params.get("discharge_coeff", 0.6)
    a_out = params.get("outlet_area_m2", 0.01)
    q_in = params.get("q_in_m3s", 0.01)
    title = params.get("title", "双容水箱系统示意图")
    g = 9.81

    fig, ax = plt.subplots(1, 1, figsize=(9, 5.5), dpi=120)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.set_aspect("equal")
    ax.axis("off")

    # Tank body
    tx, ty, tw, th = 3, 0.5, 4, 5
    tank = mpatches.FancyBboxPatch(
        (tx, ty), tw, th, boxstyle="round,pad=0.1",
        facecolor="#e8f4fd", edgecolor="#2196F3", linewidth=2.5)
    ax.add_patch(tank)

    # Water fill
    wr = h0 / h_max
    wh = th * wr
    water = mpatches.Rectangle(
        (tx + 0.15, ty + 0.15), tw - 0.3, wh,
        facecolor="#64B5F6", alpha=0.6, edgecolor="none")
    ax.add_patch(water)

    # Water level line
    wl_y = ty + 0.15 + wh
    ax.plot([tx + 0.15, tx + tw - 0.15], [wl_y, wl_y],
            color="#1565C0", linewidth=2, linestyle="--")
    ax.annotate(f"h\u2080 = {h0}m", xy=(tx + tw + 0.2, wl_y),
                fontsize=11, color="#1565C0", fontweight="bold", va="center")

    # h_max annotation
    ax.annotate(f"h_max = {h_max}m", xy=(tx + tw + 0.2, ty + th - 0.1),
                fontsize=9, color="#EF5350", va="top")

    # Inlet arrow
    ax.annotate("", xy=(tx + 1, ty + th + 0.3),
                xytext=(tx - 1.5, ty + th + 0.3),
                arrowprops=dict(arrowstyle="-|>", color="#4CAF50", lw=2.5))
    ax.text(tx - 1.2, ty + th + 0.7,
            f"Q_in = {q_in:.4f} m\u00b3/s", fontsize=10,
            color="#2E7D32", fontweight="bold")

    # Outlet arrow
    ax.annotate("", xy=(tx + tw + 1.8, ty + 0.5),
                xytext=(tx + tw, ty + 0.5),
                arrowprops=dict(arrowstyle="-|>", color="#F44336", lw=2.5))
    q_out0 = cd * a_out * math.sqrt(2 * g * h0)
    ax.text(tx + tw + 0.3, ty + 0.9,
            f"Q_out = {q_out0:.4f} m\u00b3/s", fontsize=9,
            color="#C62828", fontweight="bold")
    ax.text(tx + tw + 0.3, ty + 0.1,
            "Torricelli\u51FA\u6D41", fontsize=8, color="#888")

    # Parameter box
    info = (
        f"\u6c34\u7bb1\u53c2\u6570\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\u622a\u9762\u79ef A = {area} m\u00b2\n"
        f"\u6d41\u91cf\u7cfb\u6570 Cd = {cd}\n"
        f"\u51fa\u53e3\u9762\u79ef a = {a_out} m\u00b2\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"dh/dt = (Q_in-Q_out)/A\n"
        f"Q_out = Cd\u00b7a\u00b7\u221a(2gh)"
    )
    ax.text(0.15, 2.8, info, fontsize=9, fontfamily="monospace",
            fontproperties=font,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFF8E1",
                      edgecolor="#FFC107", alpha=0.9),
            va="center")

    ax.text(5, 6.5, title, fontsize=14, ha="center",
            fontweight="bold", color="#333", fontproperties=font_title)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


@router.post("/schematic")
async def render_schematic(req: SchematicRequest):
    """Generate a conceptual tank system diagram.
    生成水箱系统概念图。返回 PNG 图片。
    """
    png = await asyncio.to_thread(_render_schematic, req.model_dump())
    return StreamingResponse(io.BytesIO(png), media_type="image/png",
                             headers={"Content-Disposition": "inline; filename=tank_schematic.png"})
