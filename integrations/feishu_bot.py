"""Feishu Bot Integration — message handling and AI dialogue.
飞书机器人集成 — 消息处理与 AI 对话。

Receives messages from Feishu bot webhook, routes to HydroMAS
Orchestrator, and returns structured card responses.
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
class FeishuMessage:
    """Incoming message from Feishu. / 来自飞书的消息。"""

    msg_id: str = ""
    chat_id: str = ""
    user_id: str = ""
    text: str = ""
    msg_type: str = "text"  # text, interactive, image
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat(),
    )

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "text": self.text,
            "msg_type": self.msg_type,
            "timestamp": self.timestamp,
        }


@dataclass
class FeishuCardResponse:
    """Interactive card response for Feishu. / 飞书交互卡片响应。"""

    title: str = ""
    content: str = ""
    status: str = "info"  # info, success, warning, error
    actions: list[dict] = field(default_factory=list)

    def to_card_json(self) -> dict:
        """Convert to Feishu interactive card JSON format."""
        color_map = {
            "info": "blue",
            "success": "green",
            "warning": "orange",
            "error": "red",
        }
        elements = [
            {
                "tag": "markdown",
                "content": self.content,
            },
        ]
        if self.actions:
            action_elements = []
            for action in self.actions:
                action_elements.append({
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": action.get("label", "Action"),
                    },
                    "type": "primary",
                    "value": action.get("value", {}),
                })
            elements.append({
                "tag": "action",
                "actions": action_elements,
            })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": self.title,
                },
                "template": color_map.get(self.status, "blue"),
            },
            "elements": elements,
        }


# ---------------------------------------------------------------------------
# FeishuBotHandler
# ---------------------------------------------------------------------------

class FeishuBotHandler:
    """Handle Feishu bot messages and route to HydroMAS.
    处理飞书机器人消息并路由到 HydroMAS。

    Usage:
        handler = FeishuBotHandler(app_id="...", app_secret="...")
        response = await handler.handle_message(message)
    """

    # Command prefix → HydroMAS skill/tool mapping
    COMMAND_MAP: dict[str, str] = {
        "/水平衡": "water_balance",
        "/蒸发": "evap_optimization",
        "/泄漏": "leak_diagnosis",
        "/调度": "global_dispatch",
        "/日报": "daily_report",
        "/预报": "forecast",
        "/预警": "warning",
        "/ODD": "odd_check",
        "/balance": "water_balance",
        "/evap": "evap_optimization",
        "/leak": "leak_diagnosis",
        "/dispatch": "global_dispatch",
        "/report": "daily_report",
    }

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        webhook_url: str = "",
        orchestrator: object | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.webhook_url = webhook_url
        self._orchestrator = orchestrator
        self._token: str = ""
        self._token_expires: float = 0

    async def handle_message(self, message: FeishuMessage) -> FeishuCardResponse:
        """Process an incoming message and generate response.
        处理传入消息并生成响应。
        """
        text = message.text.strip()

        # Check for command prefix
        for cmd, skill_name in self.COMMAND_MAP.items():
            if text.startswith(cmd):
                return await self._execute_command(
                    skill_name, text[len(cmd):].strip(), message,
                )

        # Default: route to Orchestrator for natural language processing
        return await self._route_to_orchestrator(text, message)

    def _get_orchestrator(self):
        """Get orchestrator — injected singleton or fallback to new instance."""
        if self._orchestrator is not None:
            return self._orchestrator
        from agents.orchestrator import OrchestratorAgent
        return OrchestratorAgent()

    async def _execute_command(
        self,
        skill_name: str,
        args: str,
        message: FeishuMessage,
    ) -> FeishuCardResponse:
        """Execute a command by invoking the corresponding skill."""
        logger.info(
            "FeishuBot: executing command '%s' for user %s",
            skill_name, message.user_id,
        )

        try:
            orch = self._get_orchestrator()
            result = await orch.handle_request(
                f"Execute {skill_name}: {args}",
            )

            return FeishuCardResponse(
                title=f"HydroMAS — {skill_name}",
                content=_format_result(result),
                status="success",
            )
        except Exception as exc:
            logger.exception("FeishuBot command failed: %s", exc)
            return FeishuCardResponse(
                title="HydroMAS Error",
                content=f"Command failed: {exc}",
                status="error",
            )

    async def _route_to_orchestrator(
        self,
        text: str,
        message: FeishuMessage,
    ) -> FeishuCardResponse:
        """Route free-form text to the Orchestrator."""
        logger.info(
            "FeishuBot: routing to orchestrator for user %s",
            message.user_id,
        )

        try:
            orch = self._get_orchestrator()
            result = await orch.handle_request(text)

            return FeishuCardResponse(
                title="HydroMAS 水网助手",
                content=_format_result(result),
                status="success",
            )
        except Exception as exc:
            logger.exception("FeishuBot orchestrator failed: %s", exc)
            return FeishuCardResponse(
                title="HydroMAS Error",
                content=f"Request failed: {exc}",
                status="error",
            )

    def verify_webhook(self, body: dict) -> dict | None:
        """Verify Feishu webhook challenge. / 验证飞书 Webhook 挑战。"""
        if "challenge" in body:
            return {"challenge": body["challenge"]}
        return None


def _format_result(result: dict) -> str:
    """Format a HydroMAS result dict to Markdown for Feishu card."""
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return str(result)

    parts = []
    for key, value in result.items():
        if isinstance(value, dict):
            parts.append(f"**{key}**:")
            for k, v in value.items():
                parts.append(f"  - {k}: {v}")
        elif isinstance(value, list):
            parts.append(f"**{key}**: {len(value)} items")
        else:
            parts.append(f"**{key}**: {value}")
    return "\n".join(parts)
