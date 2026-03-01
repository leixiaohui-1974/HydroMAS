"""Feishu webhook API router — 飞书 Webhook 接入路由。

Endpoints:
    POST /api/feishu/webhook       — Receive Feishu bot event (message or challenge)
    POST /api/feishu/alert         — Send alert via Feishu webhook
    GET  /api/feishu/alert/history — Get alert history
    POST /api/feishu/sync/flush    — Flush pending Bitable sync records
    GET  /api/feishu/sync/schemas  — Get Bitable table schemas
    GET  /api/feishu/status        — Integration health status
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from web.deps import get_feishu_bot, get_feishu_alert, get_feishu_sync, get_feishu_client
from web.models import FeishuWebhookRequest, FeishuAlertRequest

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Webhook ----------


@router.post("/webhook")
async def feishu_webhook(body: FeishuWebhookRequest):
    """Receive Feishu bot callback event.
    接收飞书机器人回调事件。

    Handles two cases:
    1. Challenge verification (Feishu sends { "challenge": "..." })
    2. Message event (Feishu sends { "event": { "message": { ... } } })
    """
    handler = get_feishu_bot()

    # Challenge verification
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
