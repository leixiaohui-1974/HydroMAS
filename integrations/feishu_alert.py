"""Feishu Alert Integration — push alert cards to Feishu groups.
飞书告警集成 — 向飞书群推送告警卡片。

Converts HydroMAS SafetyAgent violations and anomaly detections
into Feishu interactive cards and sends via webhook.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AlertEvent:
    """An alert event from HydroMAS. / HydroMAS 告警事件。"""

    alert_id: str = ""
    severity: str = "info"  # info, warning, critical
    source: str = ""  # agent or skill name
    dimension: str = ""  # ODD dimension or metric name
    message: str = ""
    value: float = 0.0
    threshold: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat(),
    )
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "source": self.source,
            "dimension": self.dimension,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "actions": self.actions,
        }


# ---------------------------------------------------------------------------
# Alert card builder
# ---------------------------------------------------------------------------

SEVERITY_ICONS = {
    "info": "📋",
    "warning": "⚠️",
    "critical": "🚨",
}

SEVERITY_COLORS = {
    "info": "blue",
    "warning": "orange",
    "critical": "red",
}


def build_alert_card(event: AlertEvent) -> dict:
    """Build a Feishu interactive card from an AlertEvent.
    从 AlertEvent 构建飞书交互卡片。
    """
    icon = SEVERITY_ICONS.get(event.severity, "📋")
    color = SEVERITY_COLORS.get(event.severity, "blue")

    elements = [
        {
            "tag": "markdown",
            "content": (
                f"**时间**: {event.timestamp}\n"
                f"**来源**: {event.source}\n"
                f"**维度**: {event.dimension}\n"
                f"**当前值**: {event.value}\n"
                f"**阈值**: {event.threshold}\n"
                f"**详情**: {event.message}"
            ),
        },
    ]

    if event.actions:
        action_buttons = []
        for action_label in event.actions:
            action_buttons.append({
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": action_label,
                },
                "type": "primary" if "诊断" in action_label else "default",
                "value": {"action": action_label, "alert_id": event.alert_id},
            })
        elements.append({
            "tag": "action",
            "actions": action_buttons,
        })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{icon} {event.severity.upper()}: {event.dimension}",
                },
                "template": color,
            },
            "elements": elements,
        },
    }


# ---------------------------------------------------------------------------
# FeishuAlertSender
# ---------------------------------------------------------------------------

class FeishuAlertSender:
    """Send alert cards to Feishu group via webhook.
    通过 Webhook 向飞书群发送告警卡片。

    Usage:
        sender = FeishuAlertSender(webhook_url="https://...")
        sender.send_alert(alert_event)
    """

    def __init__(self, webhook_url: str = "") -> None:
        self.webhook_url = webhook_url
        self._history: list[AlertEvent] = []

    def send_alert(self, event: AlertEvent) -> dict:
        """Send an alert to Feishu. Returns the card payload.
        向飞书发送告警。返回卡片 payload。

        In production, this would POST to the webhook URL.
        Currently returns the payload for testing.
        """
        card = build_alert_card(event)
        self._history.append(event)

        logger.info(
            "FeishuAlert: sending %s alert for %s (id=%s)",
            event.severity, event.dimension, event.alert_id,
        )

        if self.webhook_url:
            # Production: POST to webhook
            # requests.post(self.webhook_url, json=card)
            logger.info(
                "FeishuAlert: would POST to %s", self.webhook_url,
            )

        return card

    def send_from_safety_result(self, safety_result: dict) -> list[dict]:
        """Convert SafetyAgent result to alerts and send.
        将 SafetyAgent 结果转为告警并发送。
        """
        cards = []
        violations = safety_result.get("violations", [])

        for i, v in enumerate(violations):
            event = AlertEvent(
                alert_id=f"SAFE-{datetime.now().strftime('%H%M%S')}-{i:02d}",
                severity="critical" if v.get("zone") == "red" else "warning",
                source="SafetyAgent",
                dimension=v.get("dimension", "unknown"),
                message=v.get("message", "ODD violation detected"),
                value=v.get("value", 0),
                threshold=v.get("threshold", 0),
                actions=["一键诊断", "人工确认", "忽略"],
            )
            card = self.send_alert(event)
            cards.append(card)

        return cards

    def send_from_leak_result(self, leak_result: dict) -> dict | None:
        """Convert leak detection result to alert and send.
        将泄漏检测结果转为告警并发送。
        """
        if not leak_result.get("leak_detected"):
            return None

        event = AlertEvent(
            alert_id=f"LEAK-{datetime.now().strftime('%H%M%S')}",
            severity="critical",
            source="LeakDiagnosisSkill",
            dimension="pipe_integrity",
            message=f"Leak detected: {leak_result.get('location', 'unknown')}",
            value=leak_result.get("residual", 0),
            threshold=leak_result.get("threshold", 0),
            actions=["定位泄漏", "生成工单", "联系专家"],
        )
        return self.send_alert(event)

    def get_history(self) -> list[dict]:
        """Get alert history. / 获取告警历史。"""
        return [e.to_dict() for e in self._history]
