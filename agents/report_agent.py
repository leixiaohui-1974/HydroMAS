"""Report Agent — structured report generation.
报告 Agent — 结构化报告生成。

Generates Markdown reports summarizing analysis results,
control performance, and system assessments.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


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
**Controller Type**: {ctrl_type}
**Setpoint**: {ctrl.get("setpoint", "N/A")} m

## Performance Metrics / 性能指标

| Metric | Value |
|--------|-------|
"""
        for key, value in metrics.items():
            if value is not None:
                report += f"| {key} | {value:.4f} |\n"
            else:
                report += f"| {key} | N/A |\n"

        report += f"""
## Simulation Summary / 仿真概要

- Duration: {ctrl.get("metadata", {}).get("steps", 0) * ctrl.get("metadata", {}).get("dt", 1)} s
- Solver: {ctrl.get("metadata", {}).get("solver", "N/A")}
- Final water level: {ctrl.get("water_level", [0])[-1]:.4f} m
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

- **Zone**: {status.get("zone", "unknown")}
- **Violations**: {status.get("n_violations", 0)}

## Boundary Scan Results / 边界扫描结果

- Scenarios tested: {summary.get("scenarios_tested", 0)}
- Scenarios with violations: {summary.get("scenarios_with_violations", 0)}
- **Safety Rating**: {summary.get("safety_rating", "unknown")}
"""

        if results.get("mrc_plan"):
            mrc = results["mrc_plan"]
            report += f"""
## MRC Plan / 最小风险条件计划

- **Severity**: {mrc.get("severity", "N/A")}
- **Actions**:
"""
            for action in mrc.get("actions", []):
                report += f"  - [{action.get('priority', 'N/A')}] {action.get('description', '')}\n"

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
| Tank Area | {summary.get("tank_area", "N/A")} m² |
| Controller | {summary.get("controller", "N/A")} |
| Setpoint | {summary.get("setpoint", "N/A")} m |
| ODD Zone | {summary.get("odd_zone", "N/A")} |

## Performance Evaluation / 性能评价

"""
        for key, value in evaluation.items():
            if isinstance(value, (int, float)):
                report += f"- **{key}**: {value:.4f}\n"
            elif value is not None:
                report += f"- **{key}**: {value}\n"

        return report
