"""Report API router. / 报告API路由。"""
from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter

from web.models import DailyReportRequest

router = APIRouter()


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
