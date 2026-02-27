"""Skill: Leak Diagnosis — leak detection and localization closed-loop.
技能：泄漏诊断 — 泄漏检测与定位闭环。

Combines water balance analysis, anomaly detection, GNN-based leak detection,
and optional acoustic sensor fusion for comprehensive leak diagnosis.
结合水量平衡分析、异常检测、基于GNN的泄漏检测及可选声学传感器融合，
实现全面泄漏诊断。
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class LeakDiagnosisSkill(BaseSkill):
    """Leak Diagnosis Skill — detect and localize leaks in water networks.
    泄漏诊断 Skill — 检测和定位水网中的泄漏。

    Steps:
        1. Water balance residual calculation
        2. Anomaly detection on balance residuals
        3. GNN-based leak detection
        4. Leak localization
        5. Acoustic evidence fusion (optional, if acoustic_data provided)
        6. Return diagnosis report
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        nodes_data = params.get("nodes_data", [])
        edges_data = params.get("edges_data", [])
        graph_nodes = params.get("graph_nodes", [])
        graph_edges = params.get("graph_edges", [])
        acoustic_data = params.get("acoustic_data")

        if not nodes_data or not edges_data:
            return SkillResult(success=False, error="nodes_data and edges_data are required")

        # Step 1: Water balance residual calculation
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

        # Step 2: Anomaly detection on balance residuals
        anomaly_result = await self.call_tool("detect_balance_anomaly", {
            "balance_data": balance_result,
        })
        if isinstance(anomaly_result, dict) and "error" in anomaly_result:
            return SkillResult(
                success=False,
                error=f"Anomaly detection failed: {anomaly_result['error']}",
            )
        steps.append("anomaly_detection")

        # Step 3: GNN-based leak detection
        if not graph_nodes:
            graph_nodes = nodes_data
        if not graph_edges:
            graph_edges = edges_data

        leak_result = await self.call_tool("detect_leak", {
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
        })
        if isinstance(leak_result, dict) and "error" in leak_result:
            return SkillResult(
                success=False,
                error=f"Leak detection failed: {leak_result['error']}",
            )
        steps.append("gnn_leak_detection")

        # Step 4: Leak localization
        localization_result = await self.call_tool("localize_leak", {
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
            "leak_scores": leak_result.get("leak_scores", []),
        })
        if isinstance(localization_result, dict) and "error" in localization_result:
            return SkillResult(
                success=False,
                error=f"Leak localization failed: {localization_result['error']}",
            )
        steps.append("leak_localization")

        # Step 5: Acoustic evidence fusion (optional)
        fusion_result = {}
        if acoustic_data:
            fusion_result = await self.call_tool("fuse_leak_evidence", {
                "leak_candidates": localization_result.get("candidates", []),
                "acoustic_data": acoustic_data,
            })
            if isinstance(fusion_result, dict) and "error" in fusion_result:
                return SkillResult(
                    success=False,
                    error=f"Acoustic fusion failed: {fusion_result['error']}",
                )
            steps.append("acoustic_fusion")

        # Step 6: Build diagnosis report
        diagnosis = self._build_diagnosis(
            balance_result, anomaly_result, leak_result,
            localization_result, fusion_result,
        )

        return SkillResult(
            success=True,
            data={
                "diagnosis": diagnosis,
                "balance": balance_result,
                "anomalies": anomaly_result,
                "leak_detection": leak_result,
                "localization": localization_result,
                "acoustic_fusion": fusion_result,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _build_diagnosis(
        balance: dict,
        anomalies: dict,
        leak: dict,
        localization: dict,
        fusion: dict,
    ) -> dict:
        """Build a unified diagnosis summary from all analysis results.
        从所有分析结果构建统一诊断摘要。
        """
        has_anomaly = bool(anomalies.get("anomalies", []))
        has_leak = bool(leak.get("leak_detected", False))
        candidates = localization.get("candidates", [])
        fused_candidates = fusion.get("fused_candidates", candidates)

        if has_leak and fused_candidates:
            severity = "high"
            summary = (
                f"Leak detected with {len(fused_candidates)} candidate location(s). "
                "检测到泄漏，存在候选泄漏位置。"
            )
        elif has_anomaly:
            severity = "medium"
            summary = (
                "Balance anomalies detected but no confirmed leak. "
                "检测到水量平衡异常但未确认泄漏。"
            )
        else:
            severity = "low"
            summary = "No significant anomalies or leaks detected. 未检测到显著异常或泄漏。"

        return {
            "severity": severity,
            "summary": summary,
            "has_anomaly": has_anomaly,
            "has_leak": has_leak,
            "candidate_count": len(fused_candidates),
            "candidates": fused_candidates,
        }
