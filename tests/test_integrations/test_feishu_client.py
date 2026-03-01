"""Tests for Feishu HTTP client — token management, signature, retry.
飞书 HTTP 客户端测试 — 令牌管理、签名验证、重试逻辑。
"""

from __future__ import annotations

import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import patch

import pytest

from integrations.feishu_client import FeishuClient, FeishuResponse


# ---------------------------------------------------------------------------
# FeishuResponse tests
# ---------------------------------------------------------------------------

class TestFeishuResponse:
    def test_default_ok(self):
        resp = FeishuResponse()
        assert resp.ok is True
        assert resp.code == 0

    def test_to_dict(self):
        resp = FeishuResponse(ok=False, code=99, msg="fail")
        d = resp.to_dict()
        assert d["ok"] is False
        assert d["code"] == 99
        assert d["msg"] == "fail"


# ---------------------------------------------------------------------------
# Signature verification tests
# ---------------------------------------------------------------------------

class TestSignatureVerification:
    def test_verify_signature_valid(self):
        client = FeishuClient(encrypt_key="test_key_123")
        ts = "1234567890"
        nonce = "abc"
        body = '{"event": "test"}'
        content = f"{ts}{nonce}{client.encrypt_key}{body}"
        sig = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert client.verify_signature(ts, nonce, body, sig) is True

    def test_verify_signature_invalid(self):
        client = FeishuClient(encrypt_key="test_key_123")
        assert client.verify_signature("ts", "nonce", "body", "bad_sig") is False

    def test_verify_signature_no_key(self):
        client = FeishuClient()
        # No encrypt_key → always pass
        assert client.verify_signature("ts", "nonce", "body", "anything") is True

    def test_verify_token_valid(self):
        client = FeishuClient(verification_token="my_token")
        assert client.verify_token("my_token") is True

    def test_verify_token_invalid(self):
        client = FeishuClient(verification_token="my_token")
        assert client.verify_token("wrong_token") is False

    def test_verify_token_not_configured(self):
        client = FeishuClient()
        assert client.verify_token("anything") is True


# ---------------------------------------------------------------------------
# Token management tests
# ---------------------------------------------------------------------------

class TestTokenManagement:
    def test_no_credentials_returns_empty(self):
        client = FeishuClient()
        token = client.get_tenant_token()
        assert token == ""

    def test_cached_token(self):
        import time
        client = FeishuClient(app_id="test", app_secret="secret")
        client._tenant_token = "cached_token"
        client._token_expires_at = time.time() + 3600
        token = client.get_tenant_token()
        assert token == "cached_token"

    def test_expired_token_triggers_refresh(self):
        import time
        client = FeishuClient(app_id="test", app_secret="secret")
        client._tenant_token = "old"
        client._token_expires_at = time.time() - 1  # expired

        # Mock the HTTP call to return a new token
        fake_resp = FeishuResponse(
            ok=True, code=0,
            data={"tenant_access_token": "new_token", "expire": 7200},
        )
        with patch.object(client, "_http_post", return_value=fake_resp):
            token = client.get_tenant_token()
            assert token == "new_token"
            assert client._tenant_token == "new_token"


# ---------------------------------------------------------------------------
# Webhook posting tests
# ---------------------------------------------------------------------------

class TestWebhookPost:
    def test_no_url_returns_error(self):
        client = FeishuClient()
        resp = client.post_webhook("", {"msg": "test"})
        assert resp.ok is False
        assert "not configured" in resp.msg

    def test_post_webhook_with_mock(self):
        client = FeishuClient()
        fake_resp = FeishuResponse(ok=True, code=0, data={"StatusCode": 0})
        with patch.object(client, "_http_post", return_value=fake_resp) as mock_post:
            resp = client.post_webhook("https://example.com/webhook", {"msg": "test"})
            assert resp.ok is True
            mock_post.assert_called_once_with(
                "https://example.com/webhook", {"msg": "test"}, auth=False,
            )


# ---------------------------------------------------------------------------
# API methods tests
# ---------------------------------------------------------------------------

class TestAPIMethods:
    def test_post_api_builds_url(self):
        client = FeishuClient(app_id="test", app_secret="secret")
        fake_resp = FeishuResponse(ok=True, code=0, data={})
        with patch.object(client, "_http_post", return_value=fake_resp) as mock_post:
            client.post_api("/open-apis/test", {"key": "value"})
            call_args = mock_post.call_args
            assert "open.feishu.cn/open-apis/test" in call_args[0][0]

    def test_get_api_builds_url(self):
        client = FeishuClient(app_id="test", app_secret="secret")
        fake_resp = FeishuResponse(ok=True, code=0, data={})
        with patch.object(client, "_http_get", return_value=fake_resp) as mock_get:
            client.get_api("/open-apis/test", {"page": "1"})
            call_args = mock_get.call_args
            assert "page=1" in call_args[0][0]

    def test_send_message(self):
        client = FeishuClient(app_id="test", app_secret="secret")
        fake_resp = FeishuResponse(ok=True, code=0, data={})
        with patch.object(client, "_http_post", return_value=fake_resp) as mock_post:
            client.send_message("chat_123", "interactive", {"card": {}})
            call_args = mock_post.call_args
            assert "im/v1/messages" in call_args[0][0]
            assert "receive_id_type=chat_id" in call_args[0][0]

    def test_reply_message(self):
        client = FeishuClient(app_id="test", app_secret="secret")
        fake_resp = FeishuResponse(ok=True, code=0, data={})
        with patch.object(client, "_http_post", return_value=fake_resp) as mock_post:
            client.reply_message("msg_123", "text", {"text": "ok"})
            call_args = mock_post.call_args
            assert "msg_123/reply" in call_args[0][0]

    def test_bitable_create_record(self):
        client = FeishuClient(app_id="test", app_secret="secret")
        fake_resp = FeishuResponse(ok=True, code=0, data={})
        with patch.object(client, "post_api", return_value=fake_resp) as mock_api:
            client.bitable_create_record("app_token", "tbl_123", {"name": "test"})
            call_args = mock_api.call_args
            assert "app_token" in call_args[0][0]
            assert "tbl_123" in call_args[0][0]

    def test_bitable_batch_create(self):
        client = FeishuClient(app_id="test", app_secret="secret")
        fake_resp = FeishuResponse(ok=True, code=0, data={})
        with patch.object(client, "post_api", return_value=fake_resp) as mock_api:
            records = [{"name": "a"}, {"name": "b"}]
            client.bitable_batch_create("app_token", "tbl_123", records)
            call_args = mock_api.call_args
            assert "batch_create" in call_args[0][0]
            assert len(call_args[0][1]["records"]) == 2


# ---------------------------------------------------------------------------
# Integration: alert sender with client
# ---------------------------------------------------------------------------

class TestAlertSenderWithClient:
    def test_send_alert_posts_to_webhook(self):
        from integrations.feishu_alert import AlertEvent, FeishuAlertSender
        client = FeishuClient()
        fake_resp = FeishuResponse(ok=True, code=0)
        with patch.object(client, "post_webhook", return_value=fake_resp) as mock_wh:
            sender = FeishuAlertSender(
                webhook_url="https://example.com/alert",
                client=client,
            )
            event = AlertEvent(severity="warning", dimension="water_level")
            card = sender.send_alert(event)
            assert card["msg_type"] == "interactive"
            mock_wh.assert_called_once()
            assert len(sender.get_history()) == 1

    def test_send_alert_no_client_no_crash(self):
        from integrations.feishu_alert import AlertEvent, FeishuAlertSender
        sender = FeishuAlertSender(webhook_url="https://example.com/alert")
        event = AlertEvent(severity="info", dimension="test")
        card = sender.send_alert(event)
        assert card["msg_type"] == "interactive"


# ---------------------------------------------------------------------------
# Integration: bot handler with client
# ---------------------------------------------------------------------------

class TestBotHandlerWithClient:
    def test_signature_verification_pass(self):
        from integrations.feishu_bot import FeishuBotHandler
        client = FeishuClient(encrypt_key="key123")
        handler = FeishuBotHandler(client=client)

        # Compute valid signature
        ts = "1234567890"
        nonce = "abc"
        body = '{"challenge": "test_challenge"}'
        content = f"{ts}{nonce}key123{body}"
        sig = hashlib.sha256(content.encode("utf-8")).hexdigest()

        result = handler.verify_webhook(
            json.loads(body),
            timestamp=ts, nonce=nonce,
            signature=sig, raw_body=body,
        )
        assert result == {"challenge": "test_challenge"}

    def test_signature_verification_fail(self):
        from integrations.feishu_bot import FeishuBotHandler
        client = FeishuClient(encrypt_key="key123")
        handler = FeishuBotHandler(client=client)

        result = handler.verify_webhook(
            {"challenge": "test"},
            timestamp="ts", nonce="nonce",
            signature="bad_signature", raw_body="body",
        )
        assert result == {"error": "signature verification failed"}

    def test_verification_token_check(self):
        from integrations.feishu_bot import FeishuBotHandler
        client = FeishuClient(verification_token="valid_token")
        handler = FeishuBotHandler(client=client)

        result = handler.verify_webhook({"token": "wrong_token"})
        assert result == {"error": "token verification failed"}

    def test_message_dedup(self):
        import asyncio
        from integrations.feishu_bot import FeishuBotHandler, FeishuMessage

        class MockOrch:
            calls = 0
            async def handle_request(self, text, **kw):
                MockOrch.calls += 1
                return {"result": "ok"}

        handler = FeishuBotHandler(orchestrator=MockOrch())
        msg = FeishuMessage(msg_id="dup_id_123", text="hello")

        loop = asyncio.new_event_loop()
        resp1 = loop.run_until_complete(handler.handle_message(msg))
        resp2 = loop.run_until_complete(handler.handle_message(msg))
        loop.close()

        assert resp1.status == "success"
        assert resp2.status == "info"  # duplicate
        assert MockOrch.calls == 1  # only called once


# ---------------------------------------------------------------------------
# Integration: bitable sync with client
# ---------------------------------------------------------------------------

class TestBitableSyncWithClient:
    def test_flush_with_client_calls_api(self):
        from integrations.feishu_sync import FeishuBitableSync
        client = FeishuClient()
        fake_resp = FeishuResponse(ok=True, code=0, data={})
        with patch.object(client, "bitable_batch_create", return_value=fake_resp) as mock_bc:
            sync = FeishuBitableSync(
                app_token="my_app_token",
                client=client,
            )
            sync.sync_water_kpi({"date": "2026-03-01"})
            sync.sync_alert({"alert_id": "A1"})
            result = sync.flush()
            assert result.records_synced == 2
            assert result.success is True
            assert mock_bc.call_count == 2  # two different tables

    def test_flush_without_client_still_works(self):
        from integrations.feishu_sync import FeishuBitableSync
        sync = FeishuBitableSync()
        sync.sync_water_kpi({"date": "2026-03-01"})
        result = sync.flush()
        assert result.records_synced == 1
        assert result.success is True

    def test_flush_api_error_reported(self):
        from integrations.feishu_sync import FeishuBitableSync
        client = FeishuClient()
        fail_resp = FeishuResponse(ok=False, code=400, msg="Bad request")
        with patch.object(client, "bitable_batch_create", return_value=fail_resp):
            sync = FeishuBitableSync(app_token="tok", client=client)
            sync.sync_water_kpi({"date": "2026-03-01"})
            result = sync.flush()
            assert result.success is False
            assert len(result.errors) == 1
            assert "Bad request" in result.errors[0]


# ---------------------------------------------------------------------------
# Deps singleton tests
# ---------------------------------------------------------------------------

class TestFeishuClientSingleton:
    def test_get_feishu_client_singleton(self):
        from web.deps import get_feishu_client
        a = get_feishu_client()
        b = get_feishu_client()
        assert a is b

    def test_feishu_bot_has_client(self):
        from web.deps import get_feishu_bot
        handler = get_feishu_bot()
        assert handler._client is not None

    def test_feishu_alert_has_client(self):
        from web.deps import get_feishu_alert
        # Need to clear singleton cache first for isolation
        sender = get_feishu_alert()
        assert sender._client is not None

    def test_feishu_sync_has_client(self):
        from web.deps import get_feishu_sync
        sync = get_feishu_sync()
        assert sync._client is not None
