"""WNAL (Water Network Autonomy Level) assessment.
水网自主运行等级（WNAL）评估。

Levels (L0-L5):
    L0: Manual operation / 人工操作
    L1: Assisted operation (sensor monitoring) / 辅助运行（传感监测）
    L2: Partial automation (single-loop control) / 部分自动化（单回路控制）
    L3: Conditional automation (multi-loop + ODD) / 有条件自动化（多回路+ODD）
    L4: High automation (AI-assisted decisions) / 高度自动化（AI辅助决策）
    L5: Full automation (no human in the loop) / 完全自动化（无人值守）
"""

from __future__ import annotations

CAPABILITY_WEIGHTS = {
    "sensing": 15,       # Sensor coverage and reliability / 传感器覆盖率和可靠性
    "communication": 10, # Data transmission / 数据传输
    "modeling": 15,      # Model accuracy / 模型精度
    "prediction": 15,    # Forecast capability / 预报能力
    "control": 20,       # Control sophistication / 控制水平
    "odd_monitoring": 15, # ODD awareness / ODD 感知
    "decision_support": 10, # AI decision support / AI 决策支持
}


LEVEL_THRESHOLDS = [
    (0, 20, "L0", "Manual operation / 人工操作"),
    (20, 40, "L1", "Assisted operation / 辅助运行"),
    (40, 55, "L2", "Partial automation / 部分自动化"),
    (55, 70, "L3", "Conditional automation / 有条件自动化"),
    (70, 85, "L4", "High automation / 高度自动化"),
    (85, 101, "L5", "Full automation / 完全自动化"),
]


def assess_wnal(capabilities: dict[str, float]) -> dict:
    """Assess WNAL level based on system capabilities.
    基于系统能力评估 WNAL 等级。

    Args:
        capabilities: Dict of {capability_name: score (0-100)} / 各能力项得分（0-100）
            Keys should be from CAPABILITY_WEIGHTS.

    Returns:
        Dict with WNAL level, total score, per-capability analysis, and gaps.
    """
    total_score = 0.0
    max_possible = sum(CAPABILITY_WEIGHTS.values())
    details = []
    gaps = []

    for cap_name, weight in CAPABILITY_WEIGHTS.items():
        score = capabilities.get(cap_name, 0.0)
        score = max(0.0, min(100.0, score))  # clamp to [0, 100]
        weighted = score * weight / 100.0
        total_score += weighted

        detail = {
            "capability": cap_name,
            "raw_score": score,
            "weight": weight,
            "weighted_score": round(weighted, 2),
        }
        details.append(detail)

        if score < 60:
            gaps.append({
                "capability": cap_name,
                "current_score": score,
                "target_score": 60,
                "gap": round(60 - score, 1),
                "improvement_impact": round(weight * (60 - score) / 100, 2),
            })

    # Normalize to 0-100
    normalized_score = total_score / max_possible * 100

    # Determine level
    level = "L0"
    level_desc = "Manual operation"
    for lo, hi, lvl, desc in LEVEL_THRESHOLDS:
        if lo <= normalized_score < hi:
            level = lvl
            level_desc = desc
            break

    # Sort gaps by improvement impact
    gaps.sort(key=lambda g: g["improvement_impact"], reverse=True)

    return {
        "level": level,
        "level_description": level_desc,
        "score": round(normalized_score, 1),
        "total_weighted": round(total_score, 2),
        "max_possible": max_possible,
        "details": details,
        "gaps": gaps,
        "recommendations": _generate_recommendations(level, gaps),
    }


def _generate_recommendations(level: str, gaps: list[dict]) -> list[str]:
    """Generate upgrade recommendations based on current gaps.
    根据当前差距生成升级建议。
    """
    recommendations = []

    if gaps:
        top_gap = gaps[0]
        recommendations.append(
            f"Priority: improve {top_gap['capability']} "
            f"(current {top_gap['current_score']:.0f} → target {top_gap['target_score']:.0f})"
        )

    level_num = int(level[1])
    if level_num < 3:
        recommendations.append("Add ODD monitoring capability for L3 / 添加 ODD 监测能力以达到 L3")
    if level_num < 4:
        recommendations.append("Integrate AI decision support for L4 / 集成 AI 决策支持以达到 L4")
    if level_num < 5:
        recommendations.append(
            "Achieve full redundancy and self-healing for L5"
            " / 实现完全冗余和自愈以达到 L5"
        )

    return recommendations
