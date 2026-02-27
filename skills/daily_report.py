"""Skill: Daily Report — generate daily operation report for the water network.
技能：日报 — 生成水网日常运营报告。

Aggregates water balance, anomaly detection, KPI evaluation, and evaporation
data into a structured Markdown report for daily operational review.
汇总水量平衡、异常检测、KPI评估和蒸发数据，生成结构化Markdown日报。
"""

from __future__ import annotations

from datetime import datetime

from skills.base_skill import BaseSkill, SkillResult


class DailyReportSkill(BaseSkill):
    """Daily Report Skill — produce a daily Markdown operation report.
    日报 Skill — 生成每日Markdown运营报告。

    Steps:
        1. Water balance calculation
        2. Anomaly detection
        3. Water KPI evaluation
        4. Total evaporation estimation
        5. Generate Markdown report
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        nodes_data = params.get("nodes_data", [])
        edges_data = params.get("edges_data", [])
        balance_data = params.get("balance_data", {})
        tower_params = params.get("tower_params", {})
        weather = params.get("weather", {})
        calc_params = params.get("calc_params", {})
        mud_params = params.get("mud_params", {})
        date = params.get("date", datetime.now().strftime("%Y-%m-%d"))

        if not nodes_data or not edges_data:
            return SkillResult(success=False, error="nodes_data and edges_data are required")

        # Step 1: Water balance calculation
        balance_result = await self.call_tool("calc_full_plant_balance", {
            "nodes_data": nodes_data,
            "edges_data": edges_data,
        })
        if isinstance(balance_result, dict) and "error" in balance_result:
            return SkillResult(
                success=False,
                error=f"Water balance calculation failed: {balance_result['error']}",
            )
        steps.append("water_balance")

        # Step 2: Anomaly detection
        anomaly_result = await self.call_tool("detect_balance_anomaly", {
            "balance_data": balance_result,
        })
        if isinstance(anomaly_result, dict) and "error" in anomaly_result:
            return SkillResult(
                success=False,
                error=f"Anomaly detection failed: {anomaly_result['error']}",
            )
        steps.append("anomaly_detection")

        # Step 3: Water KPI evaluation
        kpi_result = await self.call_tool("evaluate_water_kpi", {
            "balance_data": balance_data if balance_data else balance_result,
        })
        if isinstance(kpi_result, dict) and "error" in kpi_result:
            return SkillResult(
                success=False,
                error=f"KPI evaluation failed: {kpi_result['error']}",
            )
        steps.append("kpi_evaluation")

        # Step 4: Total evaporation estimation
        evap_result = await self.call_tool("predict_total_evap_loss", {
            "tower_params": tower_params,
            "weather": weather,
            "calc_params": calc_params,
            "mud_params": mud_params,
        })
        if isinstance(evap_result, dict) and "error" in evap_result:
            return SkillResult(
                success=False,
                error=f"Evaporation estimation failed: {evap_result['error']}",
            )
        steps.append("evaporation_estimation")

        # Step 5: Generate Markdown report
        report = self._generate_report(
            date, balance_result, anomaly_result, kpi_result, evap_result,
        )
        steps.append("report_generation")

        return SkillResult(
            success=True,
            data={
                "report_markdown": report,
                "date": date,
                "balance": balance_result,
                "anomalies": anomaly_result,
                "kpi": kpi_result,
                "evaporation": evap_result,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _generate_report(
        date: str,
        balance: dict,
        anomalies: dict,
        kpi: dict,
        evap: dict,
    ) -> str:
        """Generate a Markdown daily operation report.
        生成Markdown每日运营报告。
        """
        anomaly_list = anomalies.get("anomalies", [])
        anomaly_count = len(anomaly_list)
        total_evap = evap.get("total_evap_loss", 0.0)
        total_input = balance.get("total_input", 0.0)
        total_output = balance.get("total_output", 0.0)
        residual = balance.get("residual", 0.0)

        # KPI section
        kpi_lines = []
        for key, value in kpi.items():
            if isinstance(value, (int, float)):
                kpi_lines.append(f"| {key} | {value:.4f} |")
            else:
                kpi_lines.append(f"| {key} | {value} |")
        kpi_table = "\n".join(kpi_lines) if kpi_lines else "| N/A | N/A |"

        # Anomaly section
        if anomaly_list:
            anomaly_entries = "\n".join(
                f"- **{a.get('node', 'Unknown')}**: {a.get('description', 'Anomaly detected')}"
                for a in anomaly_list
            )
        else:
            anomaly_entries = "- No anomalies detected. 未检测到异常。"

        report = f"""# Daily Operation Report / 日运营报告
## Date / 日期: {date}

---

## 1. Water Balance / 水量平衡

| Metric / 指标 | Value / 值 |
|---|---|
| Total Input / 总入水 | {total_input:.2f} m³ |
| Total Output / 总出水 | {total_output:.2f} m³ |
| Residual / 残差 | {residual:.2f} m³ |

---

## 2. Anomaly Detection / 异常检测

**Anomalies found / 检测到异常数**: {anomaly_count}

{anomaly_entries}

---

## 3. KPI Evaluation / KPI评估

| KPI | Value / 值 |
|---|---|
{kpi_table}

---

## 4. Evaporation / 蒸发损失

| Metric / 指标 | Value / 值 |
|---|---|
| Total Evaporation / 总蒸发 | {total_evap:.2f} m³/d |

---

*Report generated by HydroOS DailyReportSkill / 由 HydroOS 日报技能自动生成*
"""
        return report
