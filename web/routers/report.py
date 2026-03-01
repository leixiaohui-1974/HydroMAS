"""Report API router. / 报告API路由。"""
from __future__ import annotations

import asyncio
import math
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from web.models import DailyReportRequest

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# Tank Analysis endpoint — cognitive agent chain
# ══════════════════════════════════════════════════════════════

class TankAnalysisRequest(BaseModel):
    duration: float = 300.0
    dt: float = 1.0
    initial_h: float = 0.5
    q_in_profile: Optional[list[list[float]]] = None
    tank_params: Optional[dict] = None
    solver: str = "rk4"
    title: str = "双容水箱仿真分析"


@router.post("/tank-analysis")
async def tank_analysis(req: TankAnalysisRequest):
    """Comprehensive tank simulation + cognitive analysis.

    Chain: simulate → physical analysis → ODD check → insight → report.
    综合水箱仿真分析：仿真 → 物理分析 → ODD检查 → 认知解读 → 报告。
    """
    from core.config import load_tank_config
    from mcp_servers.simulation_server import simulate_tank

    # Load defaults
    config = load_tank_config()
    tp = req.tank_params or config.get("tank_params", {})
    area = tp.get("area", 1.0)
    cd = tp.get("cd", 0.6)
    a_out = tp.get("outlet_area", 0.01)
    h_max = tp.get("h_max", 2.0)
    h_min = tp.get("h_min", 0.0)
    g = 9.81

    # ── Step 1: Simulation ──
    sim = await asyncio.to_thread(
        simulate_tank,
        duration=req.duration,
        dt=req.dt,
        initial_h=req.initial_h,
        q_in_profile=req.q_in_profile,
        tank_params=req.tank_params,
        solver=req.solver,
    )

    wl = sim["water_level"]
    outflow = sim.get("outflow", [])
    inflow = sim.get("inflow", [])
    time_arr = sim["time"]
    n = len(wl)

    # ── Step 2: Physical analysis ──
    h0, hf = wl[0], wl[-1]
    h_max_sim, h_min_sim = max(wl), min(wl)
    dh = hf - h0
    dV = dh * area  # volume change (m³)

    # Mass balance check
    q_in_total = sum(inflow) * req.dt if inflow else 0
    q_out_total = sum(outflow) * req.dt if outflow else 0
    mass_balance_error = abs(dV - (q_in_total - q_out_total))

    # Steady-state analysis
    q_in_final = inflow[-1] if inflow else 0
    q_out_final = outflow[-1] if outflow else 0
    is_steady = abs(q_in_final - q_out_final) / max(q_in_final, 0.001) < 0.01

    # Theoretical steady-state level: Q_in = Cd * a * sqrt(2*g*h_ss)
    # h_ss = (Q_in / (Cd * a))^2 / (2*g)
    if q_in_final > 0:
        h_ss = (q_in_final / (cd * a_out)) ** 2 / (2 * g)
    else:
        h_ss = 0.0

    # Time constant estimation (63.2% of step response)
    h_target = h0 + 0.632 * (hf - h0) if abs(hf - h0) > 0.001 else hf
    tau = None
    for i, h in enumerate(wl):
        if (dh > 0 and h >= h_target) or (dh < 0 and h <= h_target):
            tau = time_arr[i]
            break

    # Response characterization
    if abs(dh) < 0.001:
        response_type = "平衡态（初始即稳态）"
    elif is_steady:
        response_type = "趋于稳态"
    elif dh < 0:
        response_type = "衰减过程（出流>入流）"
    else:
        response_type = "充水过程（入流>出流）"

    # ── Step 3: ODD boundary check ──
    odd_status = "正常"
    odd_violations = []
    margin_high = (h_max - h_max_sim) / h_max * 100
    margin_low = (h_min_sim - h_min) / h_max * 100 if h_min == 0 else ((h_min_sim - h_min) / (h_max - h_min) * 100)

    if h_max_sim > h_max * 0.9:
        odd_violations.append(f"水位接近上限（{h_max_sim:.3f}m / {h_max}m，裕度{margin_high:.1f}%）")
        odd_status = "预警"
    if h_min_sim < h_max * 0.05:
        odd_violations.append(f"水位接近下限（{h_min_sim:.3f}m，裕度{margin_low:.1f}%）")
        odd_status = "预警"
    if h_max_sim > h_max:
        odd_violations.append(f"水位超限溢出！（{h_max_sim:.3f}m > {h_max}m）")
        odd_status = "危险"
    if h_min_sim < h_min:
        odd_violations.append(f"水位低于最低限！（{h_min_sim:.3f}m < {h_min}m）")
        odd_status = "危险"
    if not odd_violations:
        odd_violations.append("所有维度在安全范围内")

    # ── Step 4: Cognitive insights ──
    insights = []
    # Torricelli discharge insight
    q_out_init = cd * a_out * math.sqrt(2 * g * h0)
    insights.append(
        f"初始出流由 Torricelli 公式决定：Q_out = {cd}×{a_out}×√(2×{g}×{h0:.2f}) = {q_out_init:.6f} m³/s"
    )

    if dh < -0.1:
        insights.append(
            f"水位下降 {abs(dh):.3f}m（{abs(dh)/h0*100:.1f}%），"
            f"原因：初始出流（{q_out_init:.4f} m³/s）大于入流（{inflow[0] if inflow else 0:.4f} m³/s），"
            f"随水位下降出流逐渐减小，最终趋于平衡。"
        )
    elif dh > 0.1:
        insights.append(
            f"水位上升 {dh:.3f}m，入流持续大于出流，水箱蓄水。"
        )

    if is_steady:
        insights.append(
            f"系统已达稳态，理论平衡水位 h_ss = {h_ss:.4f}m "
            f"（实际 {hf:.4f}m，误差 {abs(hf-h_ss):.4f}m）。"
        )

    if tau:
        insights.append(f"系统时间常数约 τ ≈ {tau:.0f}s（{tau/60:.1f}min），表征响应速度。")

    # Engineering recommendation
    recommendations = []
    if margin_high < 20:
        recommendations.append("水位裕度不足，建议增大水箱面积或提高出水能力")
    if not is_steady and req.duration < 600:
        recommendations.append(f"仿真时长 {req.duration}s 可能不足以观察完整动态，建议延长至 {max(600, req.duration*2):.0f}s")
    if is_steady and abs(hf - 1.0) > 0.3:
        recommendations.append(f"稳态水位 {hf:.3f}m 偏离常用目标水位 1.0m，可通过调节入流改善")

    # ── Assemble result ──
    return {
        "title": req.title,
        "generated_at": datetime.now().isoformat(),
        "simulation": {
            "time": sim["time"],
            "water_level": sim["water_level"],
            "outflow": sim.get("outflow", []),
            "inflow": sim.get("inflow", []),
            "metadata": sim.get("metadata", {}),
        },
        "parameters": {
            "tank_area_m2": area,
            "discharge_coeff": cd,
            "outlet_area_m2": a_out,
            "h_max_m": h_max,
            "h_min_m": h_min,
            "initial_h_m": req.initial_h,
            "duration_s": req.duration,
            "dt_s": req.dt,
            "solver": req.solver,
            "inflow_type": "constant" if not req.q_in_profile else "profile",
            "q_in_m3s": inflow[0] if inflow else 0,
        },
        "analysis": {
            "response_type": response_type,
            "initial_h": h0,
            "final_h": hf,
            "h_change": dh,
            "volume_change_m3": dV,
            "h_max_sim": h_max_sim,
            "h_min_sim": h_min_sim,
            "h_steady_state_theory": h_ss,
            "is_steady_state": is_steady,
            "time_constant_s": tau,
            "mass_balance_error_m3": mass_balance_error,
            "q_in_total_m3": q_in_total,
            "q_out_total_m3": q_out_total,
        },
        "odd_check": {
            "status": odd_status,
            "violations": odd_violations,
            "margin_high_pct": round(margin_high, 1),
            "margin_low_pct": round(margin_low, 1),
        },
        "insights": insights,
        "recommendations": recommendations,
    }


@router.post("/daily")
async def generate_daily_report(req: DailyReportRequest):
    """Generate daily operations report. / 生成日运营报告。"""

    def _build_report(report_date: str, sections: list[str]) -> dict:
        """Build a daily report from available data sources.
        从可用数据源构建日运营报告。
        """
        report: dict = {
            "date": report_date,
            "sections": {},
            "generated_at": date.today().isoformat(),
        }

        if "balance" in sections:
            report["sections"]["balance"] = {
                "title": "水平衡概览",
                "status": "pending_data",
                "description": "全厂水平衡核算结果",
            }

        if "anomaly" in sections:
            report["sections"]["anomaly"] = {
                "title": "异常检测",
                "status": "pending_data",
                "description": "管网异常与泄漏检测结果",
            }

        if "kpi" in sections:
            report["sections"]["kpi"] = {
                "title": "关键指标",
                "status": "pending_data",
                "description": "日运营KPI指标汇总",
            }

        if "evaporation" in sections:
            report["sections"]["evaporation"] = {
                "title": "蒸发损耗",
                "status": "pending_data",
                "description": "冷却塔及工艺蒸发预测",
            }

        if "reuse" in sections:
            report["sections"]["reuse"] = {
                "title": "回用水优化",
                "status": "pending_data",
                "description": "回用水调度与经济性分析",
            }

        return report

    return await asyncio.to_thread(
        _build_report,
        report_date=req.date,
        sections=req.include_sections,
    )
