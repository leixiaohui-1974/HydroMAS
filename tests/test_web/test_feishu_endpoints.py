"""Tests for Feishu webhook API endpoints.
飞书 Webhook API 端点测试。

Tests the /api/feishu/* endpoints end-to-end through FastAPI TestClient.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web.app import app

client = TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Webhook — challenge verification
# ===========================================================================

class TestFeishuWebhookChallenge:
    def test_challenge_response(self):
        """Feishu sends challenge during webhook setup; we must echo it."""
        resp = client.post(
            "/api/feishu/webhook",
            json={"raw_body": {"challenge": "test_challenge_123"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["challenge"] == "test_challenge_123"

    def test_challenge_with_extra_fields(self):
        resp = client.post(
            "/api/feishu/webhook",
            json={"raw_body": {"challenge": "abc", "token": "tok", "type": "url_verification"}},
        )
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "abc"


# ===========================================================================
# Webhook — message events
# ===========================================================================

class TestFeishuWebhookMessage:
    def test_text_message_event(self):
        """Simulate a text message event from Feishu."""
        payload = {
            "raw_body": {
                "event": {
                    "message": {
                        "message_id": "msg_001",
                        "chat_id": "chat_001",
                        "message_type": "text",
                        "content": '{"text": "你好"}',
                    },
                    "sender": {
                        "sender_id": {"user_id": "user_001"},
                    },
                },
            },
        }
        resp = client.post("/api/feishu/webhook", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "card" in data
        assert "status" in data

    def test_command_message(self):
        """Simulate a command message (e.g., /预报)."""
        payload = {
            "raw_body": {
                "event": {
                    "message": {
                        "message_id": "msg_002",
                        "chat_id": "chat_001",
                        "message_type": "text",
                        "content": '{"text": "/预报 未来三天水位"}',
                    },
                    "sender": {
                        "sender_id": {"user_id": "user_001"},
                    },
                },
            },
        }
        resp = client.post("/api/feishu/webhook", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "card" in data

    def test_empty_event(self):
        """Non-challenge, non-message event should still return 200."""
        payload = {"raw_body": {"event": {}}}
        resp = client.post("/api/feishu/webhook", json=payload)
        assert resp.status_code == 200

    def test_plain_text_content(self):
        """Message content as plain string (no JSON wrapping)."""
        payload = {
            "raw_body": {
                "event": {
                    "message": {
                        "message_id": "msg_003",
                        "content": "plain text message",
                    },
                    "sender": {"sender_id": {"user_id": "u2"}},
                },
            },
        }
        resp = client.post("/api/feishu/webhook", json=payload)
        assert resp.status_code == 200


# ===========================================================================
# Alert endpoints
# ===========================================================================

class TestFeishuAlertEndpoints:
    def test_send_alert(self):
        resp = client.post(
            "/api/feishu/alert",
            json={
                "alert_id": "A001",
                "severity": "warning",
                "dimension": "water_level",
                "message": "水位超标",
                "value": 0.95,
                "threshold": 0.90,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] is True
        assert "card" in data

    def test_send_alert_defaults(self):
        resp = client.post("/api/feishu/alert", json={})
        assert resp.status_code == 200
        assert resp.json()["sent"] is True

    def test_get_alert_history(self):
        # Send an alert first
        client.post(
            "/api/feishu/alert",
            json={"alert_id": "H001", "severity": "info"},
        )
        resp = client.get("/api/feishu/alert/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert "total" in data
        assert data["total"] >= 1


# ===========================================================================
# Sync endpoints
# ===========================================================================

class TestFeishuSyncEndpoints:
    def test_flush_empty(self):
        resp = client.post("/api/feishu/sync/flush")
        assert resp.status_code == 200
        data = resp.json()
        assert "records_synced" in data

    def test_get_schemas(self):
        resp = client.get("/api/feishu/sync/schemas")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_runs" in data
        assert "water_kpi" in data
        assert "alerts" in data
        assert "dev_tasks" in data


# ===========================================================================
# Status endpoint
# ===========================================================================

class TestFeishuStatus:
    def test_status(self):
        resp = client.get("/api/feishu/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot"]["ready"] is True
        assert data["alert"]["ready"] is True
        assert data["sync"]["ready"] is True
        assert "/水平衡" in data["bot"]["commands"]
        assert "/日报" in data["bot"]["commands"]

    def test_status_has_sync_schemas(self):
        resp = client.get("/api/feishu/status")
        data = resp.json()
        assert "pipeline_runs" in data["sync"]["table_schemas"]
