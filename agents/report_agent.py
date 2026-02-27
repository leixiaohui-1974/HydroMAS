"""Report Agent — structured report generation.
报告 Agent — 结构化报告生成。

Generates Markdown reports summarizing analysis results,
control performance, and system assessments.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _escape_md(text: str) -> str:
    """Escape markdown special characters in user-derived data."""
    if not isinstance(text, str):
        return str(text)
    return text.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


class ReportAgent:
    """Report generation agent.
    报告生成 Agent。

    Produces structured Markdown reports from analysis results.
    """

    def generate_control_report(self, results: dict) -> str:
        """Generate a control system design report.
        生成控制系统设计报告。

        Args:
            results: Output from ControlSystemDesignSkill / 控制系统设计 Skill 输出

        Returns:
            Markdown report string.
        """
        metrics = results.get("performance_metrics", {})
        ctrl = results.get("control_simulation", {})
        ctrl_type = results.get("controller_type", "Unknown")

        report = f"""# Control System Design Report / 控制系统设计报告

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Controller Type**: {_escape_md(str(ctrl_type))}
**Setpoint**: {_escape_md(str(ctrl.get("setpoint", "N/A")))} m

## Performance Metrics / 性能指标

| Metric | Value |
|--------|-------|
"""
        for key, value in metrics.items():
            safe_key = _escape_md(str(key))
            if isinstance(value, (int, float)):
                report += f"| {safe_key} | {value:.4f} |\n"
            elif value is not None:
                report += f"| {safe_key} | {_escape_md(str(value))} |\n"
            else:
                report += f"| {safe_key} | N/A |\n"

        water_levels = ctrl.get("water_level", [])
        final_level = f"{water_levels[-1]:.4f}" if water_levels else "N/A"

        metadata = ctrl.get("metadata", {})
        report += f"""
## Simulation Summary / 仿真概要

- Duration: {metadata.get("steps", 0) * metadata.get("dt", 1)} s
- Solver: {_escape_md(str(metadata.get("solver", "N/A")))}
- Final water level: {final_level} m
"""
        return report

    def generate_odd_report(self, results: dict) -> str:
        """Generate an ODD assessment report.
        生成 ODD 评估报告。

        Args:
            results: Output from ODDAssessmentSkill / ODD 评估 Skill 输出

        Returns:
            Markdown report string.
        """
        status = results.get("current_odd_status", {})
        summary = results.get("overall_assessment", {})

        report = f"""# ODD Safety Assessment Report / ODD 安全评估报告

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Current Status / 当前状态

- **Zone**: {_escape_md(str(status.get("zone", "unknown")))}
- **Violations**: {status.get("n_violations", 0)}

## Boundary Scan Results / 边界扫描结果

- Scenarios tested: {summary.get("scenarios_tested", 0)}
- Scenarios with violations: {summary.get("scenarios_with_violations", 0)}
- **Safety Rating**: {_escape_md(str(summary.get("safety_rating", "unknown")))}
"""

        if results.get("mrc_plan"):
            mrc = results["mrc_plan"]
            report += f"""
## MRC Plan / 最小风险条件计划

- **Severity**: {_escape_md(str(mrc.get("severity", "N/A")))}
- **Actions**:
"""
            for action in mrc.get("actions", []):
                report += f"  - [{_escape_md(str(action.get('priority', 'N/A')))}] {_escape_md(str(action.get('description', '')))}\n"

        return report

    def generate_lifecycle_report(self, results: dict) -> str:
        """Generate a full lifecycle report.
        生成全生命周期报告。

        Args:
            results: Output from FullLifecycleSkill / 全生命周期 Skill 输出

        Returns:
            Markdown report string.
        """
        summary = results.get("summary", {})
        evaluation = results.get("evaluation", {})

        report = f"""# Full Lifecycle Report / 全生命周期报告

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## System Summary / 系统概要

| Parameter | Value |
|-----------|-------|
| Tank Area | {_escape_md(str(summary.get("tank_area", "N/A")))} m² |
| Controller | {_escape_md(str(summary.get("controller", "N/A")))} |
| Setpoint | {_escape_md(str(summary.get("setpoint", "N/A")))} m |
| ODD Zone | {_escape_md(str(summary.get("odd_zone", "N/A")))} |

## Performance Evaluation / 性能评价

"""
        for key, value in evaluation.items():
            safe_key = _escape_md(str(key))
            if isinstance(value, (int, float)):
                report += f"- **{safe_key}**: {value:.4f}\n"
            elif value is not None:
                report += f"- **{safe_key}**: {_escape_md(str(value))}\n"

        return report

    def generate_water_balance_report(self, balance_result: dict) -> str:
        """Generate water balance report in Markdown. / 生成水平衡报告。"""
        report = f"""# Water Balance Report / 水平衡报告

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary / 概要

| Metric | Value |
|--------|-------|
| Total Intake | {balance_result.get("total_intake", 0):.1f} m³/d |
| Total Consumption | {balance_result.get("total_consumption", 0):.1f} m³/d |
| Total Loss | {balance_result.get("total_loss", 0):.1f} m³/d |
| Total Evaporation | {balance_result.get("total_evap", 0):.1f} m³/d |
| Reuse Rate | {balance_result.get("reuse_rate", 0):.1%} |
| Balance Error | {balance_result.get("balance_error", 0):.4f} |

## Node Residuals / 节点残差

"""
        residuals = balance_result.get("node_residuals", {})
        if residuals:
            report += "| Node | Residual |\n|------|----------|\n"
            for node_id, residual in residuals.items():
                report += f"| {_escape_md(str(node_id))} | {residual:.4f} |\n"
        return report

    def generate_daily_operation_report(self, daily_data: dict) -> str:
        """Generate daily operation report. / 生成日运营报告。"""
        date = daily_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        report = f"""# Daily Operation Report / 日运营报告

**Date**: {_escape_md(str(date))}
**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Water Balance / 水平衡

- Total Intake: {daily_data.get("total_intake", 0):.1f} m³/d
- Reuse Rate: {daily_data.get("reuse_rate", 0):.1%}
- Balance Error: {daily_data.get("balance_error", 0):.4f}

## KPI / 关键指标

"""
        kpi = daily_data.get("kpi", {})
        for key, value in kpi.items():
            safe_key = _escape_md(str(key))
            if isinstance(value, (int, float)):
                report += f"- **{safe_key}**: {value:.4f}\n"
            elif value is not None:
                report += f"- **{safe_key}**: {_escape_md(str(value))}\n"

        anomalies = daily_data.get("anomalies", [])
        report += f"\n## Anomalies / 异常事件\n\n"
        if anomalies:
            report += f"Detected {len(anomalies)} anomalies.\n\n"
            for a in anomalies:
                report += f"- **{_escape_md(str(a.get('node_id', 'unknown')))}**: {_escape_md(str(a.get('severity', 'unknown')))} severity\n"
        else:
            report += "No anomalies detected. / 未检测到异常。\n"

        evap = daily_data.get("evaporation", {})
        report += f"\n## Evaporation / 蒸发损耗\n\n"
        report += f"- Total Daily Evaporation: {evap.get('total_daily_m3', 0):.1f} m³/d\n"
        return report

    def generate_leak_diagnosis_report(self, diagnosis_result: dict) -> str:
        """Generate leak diagnosis report. / 生成泄漏诊断报告。"""
        diagnosis = diagnosis_result.get("diagnosis", {})
        report = f"""# Leak Diagnosis Report / 泄漏诊断报告

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Severity**: {_escape_md(str(diagnosis.get("severity", "unknown")))}
**Leak Detected**: {diagnosis.get("leak_detected", False)}

## Localization / 泄漏定位

"""
        suspects = diagnosis.get("top_suspects", diagnosis_result.get("localization", {}).get("suspects", []))
        if suspects:
            report += "| Pipe | Confidence |\n|------|------------|\n"
            for s in suspects:
                report += f"| {_escape_md(str(s.get('pipe_id', 'N/A')))} | {s.get('confidence', 0):.2%} |\n"
        else:
            report += "No specific pipe segments identified.\n"
        return report
