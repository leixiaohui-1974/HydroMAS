"""Safety Agent — ODD boundary guardian.
安全 Agent — ODD 边界守护。

Operates in two modes:
    - Passive: Called by Orchestrator to verify an operation is safe
    - Active: Continuously monitors during simulation/control for ODD violations
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SafetyAgent:
    """Safety Agent for ODD monitoring and MRC triggering.
    ODD 监测与 MRC 触发的安全 Agent。
    """

    def __init__(self, odd_config: dict | None = None):
        self.odd_config = odd_config
        self._violation_log: list[dict] = []

    def check_state(self, state: dict[str, float]) -> dict:
        """Check a single state against ODD (passive mode).
        检查单个状态是否在 ODD 内（被动模式）。

        Args:
            state: Current system state / 当前系统状态

        Returns:
            ODD check result with zone and violations.
        """
        from core.odd.odd_monitor import check_odd
        from core.odd.odd_definition import ODDSpec, create_tank_odd

        odd_spec = ODDSpec.from_dict(self.odd_config) if self.odd_config else create_tank_odd()
        result = check_odd(state, odd_spec)

        if result["violations"]:
            self._violation_log.append({
                "state": state,
                "violations": result["violations"],
                "zone": result["zone"],
            })

        return result

    def check_action_safe(self, action: dict, current_state: dict) -> dict:
        """Verify that a proposed action is safe before execution.
        在执行前验证提议的动作是否安全。

        Args:
            action: Proposed action {type, value, ...} / 提议的动作
            current_state: Current system state / 当前系统状态

        Returns:
            Safety verdict with recommendation.
        """
        result = self.check_state(current_state)

        if result["zone"] == "mrc":
            from core.odd.mrc_handler import determine_mrc_actions
            mrc_actions = determine_mrc_actions(result["violations"])
            return {
                "safe": False,
                "zone": "mrc",
                "message": "System is outside ODD. MRC actions required. / 系统已超出ODD。需要MRC动作。",
                "recommended_actions": mrc_actions,
                "proposed_action_blocked": True,
            }

        if result["zone"] == "extended":
            return {
                "safe": True,
                "zone": "extended",
                "message": "System in extended zone. Proceed with caution. / 系统在扩展域。请谨慎操作。",
                "requires_human_confirmation": True,
                "proposed_action_blocked": False,
            }

        return {
            "safe": True,
            "zone": "normal",
            "message": "System within ODD. Action approved. / 系统在ODD内。动作批准。",
            "proposed_action_blocked": False,
        }

    def monitor_series(self, states: list[dict[str, float]], times: list[float] | None = None) -> dict:
        """Monitor a series of states for ODD violations (active mode).
        监测状态序列的 ODD 越界（主动模式）。

        Args:
            states: List of system states over time / 时序状态列表
            times: Optional timestamps / 可选时间戳

        Returns:
            Monitoring summary with any violations detected.
        """
        from core.odd.odd_monitor import check_odd_series
        from core.odd.odd_definition import ODDSpec, create_tank_odd

        odd_spec = ODDSpec.from_dict(self.odd_config) if self.odd_config else create_tank_odd()
        result = check_odd_series(states, times, odd_spec)

        if result["worst_zone"] == "mrc":
            logger.warning(
                f"ODD violation detected at time {result.get('time_to_breach')}"
            )

        return result

    def get_violation_log(self) -> list[dict]:
        """Return accumulated violation log. / 返回累积的越界日志。"""
        return list(self._violation_log)

    def clear_violation_log(self) -> None:
        """Clear violation log. / 清除越界日志。"""
        self._violation_log.clear()
