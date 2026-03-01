"""Feishu Bot Integration — message handling and AI dialogue.
飞书机器人集成 — 消息处理与 AI 对话。

Receives messages from Feishu bot webhook, routes to HydroMAS
Orchestrator, and returns structured card responses.

Multi-user concurrent support (v0.2.2):
- Immediate ACK to avoid Feishu 5s timeout
- Background async processing per user
- Reply via Feishu API (reply_message or send_message)
- Per-user session isolation (channel="feishu")
- Thread-safe message dedup
- Configurable user→role mapping
- Per-user rate limiting
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from integrations.feishu_client import FeishuClient

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
# Per-user rate limiter (token bucket)
# ---------------------------------------------------------------------------

class _UserRateLimiter:
    """Simple per-user rate limiter using token bucket.
    每用户速率限制器（令牌桶）。
    """

    def __init__(self, max_tokens: int = 5, refill_per_second: float = 0.5):
        self._max = max_tokens
        self._refill_rate = refill_per_second
        self._buckets: dict[str, float] = {}
        self._last_refill: dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, user_id: str) -> bool:
        """Check if user is allowed to send a message."""
        with self._lock:
            now = time.time()

            if user_id not in self._buckets:
                # First request from user: full bucket minus 1
                self._buckets[user_id] = float(self._max - 1)
                self._last_refill[user_id] = now
                return True

            elapsed = now - self._last_refill[user_id]
            self._last_refill[user_id] = now

            # Refill tokens
            tokens = self._buckets[user_id] + elapsed * self._refill_rate
            tokens = min(tokens, float(self._max))

            if tokens >= 1:
                self._buckets[user_id] = tokens - 1
                return True
            self._buckets[user_id] = tokens
            return False

    def cleanup(self, max_idle_seconds: float = 3600) -> None:
        """Remove idle user buckets."""
        with self._lock:
            cutoff = time.time() - max_idle_seconds
            stale = [k for k, t in self._last_refill.items() if t < cutoff]
            for k in stale:
                del self._buckets[k]
                del self._last_refill[k]


# ---------------------------------------------------------------------------
# FeishuBotHandler
# ---------------------------------------------------------------------------

class FeishuBotHandler:
    """Handle Feishu bot messages and route to HydroMAS.
    处理飞书机器人消息并路由到 HydroMAS。

    Multi-user concurrent mode (v0.2.2):
    - handle_message(): sync processing, returns FeishuCardResponse
    - handle_message_async(): queues background task, returns immediately
    - Background task processes AI request and replies via Feishu API

    Usage:
        handler = FeishuBotHandler(app_id="...", app_secret="...")
        # Sync (for testing):
        response = await handler.handle_message(message)
        # Async (for production):
        ack = handler.handle_message_async(message)
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
        "/帮助": "_help",
        "/help": "_help",
    }

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        webhook_url: str = "",
        orchestrator: object | None = None,
        client: FeishuClient | None = None,
        user_roles: dict[str, str] | None = None,
        rate_limit: int = 5,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.webhook_url = webhook_url
        self._orchestrator = orchestrator
        self._client = client
        self._token: str = ""
        self._token_expires: float = 0

        # Multi-user support
        self._user_roles: dict[str, str] = user_roles or {}
        self._rate_limiter = _UserRateLimiter(max_tokens=rate_limit)
        self._active_users: dict[str, float] = {}  # user_id → last_active
        self._active_users_lock = threading.Lock()

        # Thread-safe dedup
        self._dedup_lock = threading.Lock()
        self._processed_msg_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Public: synchronous message handling (original API, for testing)
    # ------------------------------------------------------------------

    async def handle_message(self, message: FeishuMessage) -> FeishuCardResponse:
        """Process an incoming message and generate response (sync).
        处理传入消息并生成响应（同步模式）。
        """
        # Dedup: skip already-processed messages
        if self._is_duplicate(message.msg_id):
            return FeishuCardResponse(
                title="HydroMAS",
                content="(duplicate message ignored)",
                status="info",
            )

        # Rate limit check
        if not self._rate_limiter.allow(message.user_id or "anonymous"):
            return FeishuCardResponse(
                title="HydroMAS",
                content="请求过于频繁，请稍后再试。\nToo many requests, please try again later.",
                status="warning",
            )

        # Track active user
        self._track_user(message.user_id)

        text = message.text.strip()

        # Help command
        if text in ("/帮助", "/help"):
            return self._build_help_response()

        # Check for command prefix
        for cmd, skill_name in self.COMMAND_MAP.items():
            if text.startswith(cmd) and skill_name != "_help":
                return await self._execute_command(
                    skill_name, text[len(cmd):].strip(), message,
                )

        # Default: route to Orchestrator for natural language processing
        return await self._route_to_orchestrator(text, message)

    # ------------------------------------------------------------------
    # Public: async background processing (production mode)
    # ------------------------------------------------------------------

    def handle_message_async(
        self,
        message: FeishuMessage,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> dict:
        """Queue message for background processing (immediate return).
        将消息加入后台队列处理（立即返回）。

        Returns an ACK dict. The actual response will be sent via Feishu API.
        """
        # Dedup
        if self._is_duplicate(message.msg_id):
            return {"status": "duplicate", "msg_id": message.msg_id}

        # Rate limit
        if not self._rate_limiter.allow(message.user_id or "anonymous"):
            return {"status": "rate_limited", "msg_id": message.msg_id}

        self._track_user(message.user_id)

        # Schedule background task
        target_loop = loop or asyncio.get_event_loop()
        target_loop.create_task(self._process_and_reply(message))

        return {
            "status": "accepted",
            "msg_id": message.msg_id,
            "user_id": message.user_id,
        }

    async def _process_and_reply(self, message: FeishuMessage) -> None:
        """Process message in background and reply via Feishu API.
        后台处理消息并通过飞书 API 回复。
        """
        try:
            response = await self._process_message_internal(message)
            await self._reply_to_feishu(message, response)
        except Exception as exc:
            logger.exception(
                "FeishuBot: background processing failed for user %s: %s",
                message.user_id, exc,
            )
            # Try to send error response
            try:
                error_resp = FeishuCardResponse(
                    title="HydroMAS Error",
                    content=f"处理失败: {exc}",
                    status="error",
                )
                await self._reply_to_feishu(message, error_resp)
            except Exception:
                logger.error("FeishuBot: failed to send error reply")

    async def _process_message_internal(
        self, message: FeishuMessage,
    ) -> FeishuCardResponse:
        """Core message processing logic (shared by sync and async paths)."""
        text = message.text.strip()

        # Help command
        if text in ("/帮助", "/help"):
            return self._build_help_response()

        # Command routing
        for cmd, skill_name in self.COMMAND_MAP.items():
            if text.startswith(cmd) and skill_name != "_help":
                return await self._execute_command(
                    skill_name, text[len(cmd):].strip(), message,
                )

        # Natural language
        return await self._route_to_orchestrator(text, message)

    async def _reply_to_feishu(
        self, message: FeishuMessage, response: FeishuCardResponse,
    ) -> None:
        """Send response back to Feishu via API.
        通过飞书 API 将响应发送回去。
        """
        if not self._client:
            logger.debug("FeishuBot: no client, skipping API reply")
            return

        card_json = response.to_card_json()

        # Try reply_message first (reply to the original message)
        if message.msg_id:
            resp = self._client.reply_message(
                message_id=message.msg_id,
                msg_type="interactive",
                content=card_json,
            )
            if resp.ok:
                logger.info(
                    "FeishuBot: replied to msg_id=%s for user %s",
                    message.msg_id, message.user_id,
                )
                return
            logger.warning(
                "FeishuBot: reply_message failed (code=%d), trying send_message",
                resp.code,
            )

        # Fallback: send_message to chat
        if message.chat_id:
            resp = self._client.send_message(
                receive_id=message.chat_id,
                msg_type="interactive",
                content=card_json,
                receive_id_type="chat_id",
            )
            if resp.ok:
                logger.info(
                    "FeishuBot: sent to chat_id=%s for user %s",
                    message.chat_id, message.user_id,
                )
            else:
                logger.error(
                    "FeishuBot: send_message also failed: code=%d msg=%s",
                    resp.code, resp.msg,
                )

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def get_user_role(self, user_id: str) -> str:
        """Get HydroClaw role for a Feishu user.
        获取飞书用户对应的 HydroClaw 角色。

        Priority: user_roles mapping → default "operator"
        """
        return self._user_roles.get(user_id, "operator")

    def set_user_role(self, user_id: str, role: str) -> None:
        """Set HydroClaw role for a Feishu user."""
        self._user_roles[user_id] = role

    def get_active_users(self) -> dict[str, float]:
        """Get currently active Feishu users with last active time."""
        with self._active_users_lock:
            return dict(self._active_users)

    def get_active_user_count(self) -> int:
        """Get count of recently active users (within 1 hour)."""
        cutoff = time.time() - 3600
        with self._active_users_lock:
            return sum(1 for t in self._active_users.values() if t > cutoff)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_orchestrator(self):
        """Get orchestrator — injected singleton or fallback to new instance."""
        if self._orchestrator is not None:
            return self._orchestrator
        from agents.orchestrator import OrchestratorAgent
        return OrchestratorAgent()

    def _is_duplicate(self, msg_id: str) -> bool:
        """Thread-safe dedup check."""
        if not msg_id:
            return False
        with self._dedup_lock:
            if msg_id in self._processed_msg_ids:
                logger.info("FeishuBot: skipping duplicate msg_id=%s", msg_id)
                return True
            self._processed_msg_ids.add(msg_id)
            if len(self._processed_msg_ids) > 5000:
                # Keep only recent half
                recent = list(self._processed_msg_ids)[-2500:]
                self._processed_msg_ids = set(recent)
            return False

    def _track_user(self, user_id: str) -> None:
        """Track user activity."""
        if user_id:
            with self._active_users_lock:
                self._active_users[user_id] = time.time()

    def _build_help_response(self) -> FeishuCardResponse:
        """Build help card listing available commands."""
        lines = [
            "**可用命令 / Available Commands:**\n",
            "| 命令 | 说明 |",
            "|------|------|",
            "| /水平衡 | 全厂水平衡分析 |",
            "| /蒸发 | 蒸发优化分析 |",
            "| /泄漏 | 泄漏诊断 |",
            "| /调度 | 全局调度优化 |",
            "| /日报 | 生成日报 |",
            "| /预报 | 水位预报 |",
            "| /预警 | 预警分析 |",
            "| /ODD | ODD安全检查 |",
            "| /帮助 | 显示此帮助 |",
            "\n也可以直接用自然语言提问，例如：",
            '"今天水平衡情况如何？"',
            '"分析一下蒸发损失"',
        ]
        return FeishuCardResponse(
            title="HydroMAS 水网助手 — 帮助",
            content="\n".join(lines),
            status="info",
        )

    async def _execute_command(
        self,
        skill_name: str,
        args: str,
        message: FeishuMessage,
    ) -> FeishuCardResponse:
        """Execute a command by invoking the corresponding skill."""
        user_role = self.get_user_role(message.user_id)
        logger.info(
            "FeishuBot: executing command '%s' for user %s (role=%s)",
            skill_name, message.user_id, user_role,
        )

        try:
            orch = self._get_orchestrator()
            result = await orch.handle_request(
                f"Execute {skill_name}: {args}",
                user_id=message.user_id,
                role=user_role,
                session_id=f"feishu:{message.user_id}",
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
        user_role = self.get_user_role(message.user_id)
        logger.info(
            "FeishuBot: routing to orchestrator for user %s (role=%s)",
            message.user_id, user_role,
        )

        try:
            orch = self._get_orchestrator()
            result = await orch.handle_request(
                text,
                user_id=message.user_id,
                role=user_role,
                session_id=f"feishu:{message.user_id}",
            )

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

    def verify_webhook(
        self,
        body: dict,
        timestamp: str = "",
        nonce: str = "",
        signature: str = "",
        raw_body: str = "",
    ) -> dict | None:
        """Verify Feishu webhook challenge and signature.
        验证飞书 Webhook 挑战和签名。

        When encrypt_key is configured, also verifies the callback signature.
        """
        # Signature verification (when client has encrypt_key configured)
        if self._client and signature and raw_body:
            if not self._client.verify_signature(timestamp, nonce, raw_body, signature):
                logger.warning("FeishuBot: webhook signature verification failed")
                return {"error": "signature verification failed"}

        # Verification token check
        if self._client and body.get("token"):
            if not self._client.verify_token(body["token"]):
                logger.warning("FeishuBot: verification token mismatch")
                return {"error": "token verification failed"}

        # Challenge response
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
