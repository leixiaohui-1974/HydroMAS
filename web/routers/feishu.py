"""Feishu webhook API router — 飞书 Webhook 接入路由。

Multi-user concurrent support (v0.2.2):
- Webhook returns immediate ACK (avoids Feishu 5s timeout)
- AI processing runs in background task
- Response sent back via Feishu reply_message API
- Per-user session isolation
- Per-user rate limiting

Endpoints:
    POST /api/feishu/webhook       — Receive Feishu bot event (message or challenge)
    POST /api/feishu/alert         — Send alert via Feishu webhook
    GET  /api/feishu/alert/history — Get alert history
    POST /api/feishu/sync/flush    — Flush pending Bitable sync records
    GET  /api/feishu/sync/schemas  — Get Bitable table schemas
    GET  /api/feishu/status        — Integration health status
    GET  /api/feishu/users         — Active Feishu users
    POST /api/feishu/users/role    — Set user role mapping
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks

from web.deps import get_feishu_bot, get_feishu_alert, get_feishu_sync, get_feishu_client
from web.models import FeishuWebhookRequest, FeishuAlertRequest

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Webhook ----------


@router.post("/webhook")
async def feishu_webhook(body: FeishuWebhookRequest, background_tasks: BackgroundTasks):
    """Receive Feishu bot callback event.
    接收飞书机器人回调事件。

    Multi-user concurrent mode:
    1. Challenge verification → immediate response
    2. Message event → immediate ACK + background AI processing + async reply

    飞书要求 webhook 在 5 秒内响应，AI 处理通常需要更长时间，
    所以我们立即返回 ACK，后台异步处理并通过飞书 API 回复。
    """
    handler = get_feishu_bot()

    # Challenge verification (must respond immediately)
    challenge_resp = handler.verify_webhook(body.raw_body)
    if challenge_resp is not None:
        return challenge_resp

    # Extract message from event payload
    event = body.raw_body.get("event", {})
    message_data = event.get("message", {})
    sender = event.get("sender", {})

    from integrations.feishu_bot import FeishuMessage

    msg = FeishuMessage(
        msg_id=message_data.get("message_id", ""),
        chat_id=message_data.get("chat_id", ""),
        user_id=sender.get("sender_id", {}).get("user_id", ""),
        text=_extract_text(message_data),
        msg_type=message_data.get("message_type", "text"),
    )

    # Skip non-text messages
    if msg.msg_type != "text" or not msg.text.strip():
        return {"status": "ignored", "reason": "non-text or empty"}

    # Check if client is configured for async replies
    client = get_feishu_client()
    if client.app_id and client.app_secret:
        # Production mode: immediate ACK + background processing
        # Use handle_message_async which schedules background task
        try:
            loop = asyncio.get_running_loop()
            ack = handler.handle_message_async(msg, loop=loop)
        except RuntimeError:
            ack = handler.handle_message_async(msg)

        return ack
    else:
        # Dev mode (no Feishu credentials): synchronous processing
        response = await handler.handle_message(msg)
        return {
            "card": response.to_card_json(),
            "status": response.status,
            "title": response.title,
        }


@router.post("/alert")
async def send_feishu_alert(req: FeishuAlertRequest):
    """Send an alert to Feishu webhook.
    发送告警到飞书 Webhook。
    """
    from integrations.feishu_alert import AlertEvent

    sender = get_feishu_alert()
    event = AlertEvent(
        alert_id=req.alert_id,
        severity=req.severity,
        dimension=req.dimension,
        message=req.message,
        value=req.value,
        threshold=req.threshold,
    )
    card = sender.send_alert(event)
    return {"sent": True, "card": card}


@router.get("/alert/history")
async def get_alert_history():
    """Get recent alert history.
    获取近期告警历史。
    """
    sender = get_feishu_alert()
    return {"history": sender.get_history(), "total": len(sender.get_history())}


@router.post("/sync/flush")
async def flush_sync():
    """Flush pending Bitable sync records.
    刷新待同步的 Bitable 记录。
    """
    sync = get_feishu_sync()
    result = sync.flush()
    return {
        "success": result.success,
        "records_synced": result.records_synced,
        "errors": result.errors,
    }


@router.get("/sync/schemas")
async def get_sync_schemas():
    """Get Bitable table schemas.
    获取 Bitable 表结构。
    """
    sync = get_feishu_sync()
    return sync.get_table_schemas()


@router.get("/status")
async def feishu_status():
    """Get Feishu integration status.
    获取飞书集成状态。
    """
    handler = get_feishu_bot()
    sender = get_feishu_alert()
    sync = get_feishu_sync()
    client = get_feishu_client()

    return {
        "client": {
            "app_id_configured": bool(client.app_id),
            "app_secret_configured": bool(client.app_secret),
            "verification_token_configured": bool(client.verification_token),
            "encrypt_key_configured": bool(client.encrypt_key),
        },
        "bot": {
            "ready": True,
            "webhook_url_configured": bool(handler.webhook_url),
            "commands": list(handler.COMMAND_MAP.keys()),
            "active_users": handler.get_active_user_count(),
        },
        "alert": {
            "ready": True,
            "webhook_url_configured": bool(sender.webhook_url),
            "history_count": len(sender.get_history()),
        },
        "sync": {
            "ready": True,
            "app_token_configured": bool(sync.app_token),
            "table_schemas": list(sync.get_table_schemas().keys()),
        },
    }


@router.get("/users")
async def feishu_active_users():
    """Get active Feishu users and their roles.
    获取活跃的飞书用户及其角色。
    """
    handler = get_feishu_bot()
    active = handler.get_active_users()
    return {
        "active_users": {
            uid: {
                "last_active": ts,
                "role": handler.get_user_role(uid),
            }
            for uid, ts in active.items()
        },
        "total": len(active),
        "recent_1h": handler.get_active_user_count(),
    }


@router.post("/users/role")
async def set_feishu_user_role(user_id: str, role: str):
    """Set HydroClaw role for a Feishu user.
    设置飞书用户对应的 HydroClaw 角色。

    Roles: operator, designer, researcher, admin, teacher
    """
    valid_roles = {"operator", "designer", "researcher", "admin", "teacher"}
    if role not in valid_roles:
        return {
            "error": f"Invalid role '{role}'. Valid: {', '.join(sorted(valid_roles))}",
        }

    handler = get_feishu_bot()
    handler.set_user_role(user_id, role)
    return {
        "user_id": user_id,
        "role": role,
        "status": "updated",
    }


def _extract_text(message_data: dict) -> str:
    """Extract plain text from Feishu message payload.
    从飞书消息体中提取纯文本。
    """
    content = message_data.get("content", "")
    if isinstance(content, str):
        import json as _json
        try:
            parsed = _json.loads(content)
            if isinstance(parsed, dict) and "text" in parsed:
                return parsed["text"]
        except (ValueError, TypeError):
            pass
        return content
    if isinstance(content, dict) and "text" in content:
        return content["text"]
    return str(content)
