"""Minimal Risk Condition (MRC) handler for ODD violations.
最小风险条件（MRC）处理器 — ODD 越界时的安全降级。

When the system exits the ODD boundary, MRC procedures activate
to bring the system to a safe state.
"""

from __future__ import annotations

from typing import Literal


MRCAction = Literal["close_inlet", "open_drain", "emergency_stop", "alert", "reduce_inflow"]


def determine_mrc_actions(violations: list[dict]) -> list[dict]:
    """Determine MRC actions based on ODD violations.
    根据 ODD 越界情况确定 MRC 动作。

    Args:
        violations: List of violation dicts from check_odd / ODD 检查返回的越界列表

    Returns:
        List of recommended MRC actions with priority.
    """
    actions = []

    for v in violations:
        dim = v["dimension"]
        bound = v["bound_violated"]

        if dim == "water_level":
            if bound == "upper":
                actions.append({
                    "action": "close_inlet",
                    "priority": 1,
                    "description": "Close inlet valve to stop inflow / 关闭进水阀停止入流",
                    "target_dimension": dim,
                })
                actions.append({
                    "action": "open_drain",
                    "priority": 2,
                    "description": "Open emergency drain / 打开紧急排水",
                    "target_dimension": dim,
                })
            elif bound == "lower":
                actions.append({
                    "action": "reduce_inflow",
                    "priority": 1,
                    "description": "Open inlet valve for emergency fill / 打开进水阀紧急补水",
                    "target_dimension": dim,
                })

        elif dim == "structural_pressure":
            actions.append({
                "action": "emergency_stop",
                "priority": 0,
                "description": "Emergency stop: structural integrity at risk / 紧急停止：结构安全风险",
                "target_dimension": dim,
            })

        else:
            actions.append({
                "action": "alert",
                "priority": 3,
                "description": f"Alert: {dim} out of ODD bounds / 告警：{dim} 超出 ODD 边界",
                "target_dimension": dim,
            })

    # Sort by priority (lower number = higher priority)
    actions.sort(key=lambda a: a["priority"])
    return actions


def generate_mrc_plan(violations: list[dict], current_state: dict) -> dict:
    """Generate a complete MRC response plan.
    生成完整的 MRC 响应计划。

    Args:
        violations: ODD violation list / ODD 越界列表
        current_state: Current system state / 当前系统状态

    Returns:
        MRC plan with actions, timeline, and verification steps.
    """
    actions = determine_mrc_actions(violations)

    return {
        "status": "mrc_activated",
        "violations": violations,
        "actions": actions,
        "verification_steps": [
            "Monitor all ODD dimensions at 1-second intervals / 1秒间隔监测所有ODD维度",
            "Confirm system returning to ODD after 60 seconds / 60秒后确认系统回到ODD内",
            "If not recovered, escalate to human operator / 未恢复则上报人工操作员",
        ],
        "current_state": current_state,
        "severity": "critical" if any(a["priority"] == 0 for a in actions) else "high",
    }
