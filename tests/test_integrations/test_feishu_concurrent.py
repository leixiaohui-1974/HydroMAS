"""Tests for Feishu multi-user concurrent access.
飞书多用户并发访问测试。

Tests:
- Per-user rate limiting
- Thread-safe message dedup
- Async background processing
- User role mapping
- Active user tracking
- Concurrent message handling
- Webhook async flow
"""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from integrations.feishu_bot import (
    FeishuBotHandler,
    FeishuCardResponse,
    FeishuMessage,
    _UserRateLimiter,
)


# ---------------------------------------------------------------------------
# Mock orchestrator for concurrent testing
# ---------------------------------------------------------------------------

class ConcurrentMockOrchestrator:
    """Mock orchestrator that tracks concurrent calls."""

    def __init__(self, delay: float = 0.0):
        self.requests: list[dict] = []
        self.concurrent_count = 0
        self.max_concurrent = 0
        self._lock = threading.Lock()
        self._delay = delay

    async def handle_request(self, text: str, **kwargs) -> dict:
        with self._lock:
            self.concurrent_count += 1
            self.max_concurrent = max(self.max_concurrent, self.concurrent_count)
            self.requests.append({"text": text, **kwargs})

        if self._delay > 0:
            await asyncio.sleep(self._delay)

        with self._lock:
            self.concurrent_count -= 1

        return {
            "status": "completed",
            "result": f"Processed: {text}",
            "user_id": kwargs.get("user_id", ""),
        }


# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------

class TestUserRateLimiter:
    def test_allows_within_limit(self):
        limiter = _UserRateLimiter(max_tokens=3, refill_per_second=0)
        assert limiter.allow("user1") is True
        assert limiter.allow("user1") is True
        assert limiter.allow("user1") is True

    def test_blocks_over_limit(self):
        limiter = _UserRateLimiter(max_tokens=2, refill_per_second=0)
        assert limiter.allow("user1") is True
        assert limiter.allow("user1") is True
        assert limiter.allow("user1") is False  # over limit

    def test_different_users_independent(self):
        limiter = _UserRateLimiter(max_tokens=1, refill_per_second=0)
        assert limiter.allow("user1") is True
        assert limiter.allow("user2") is True
        assert limiter.allow("user1") is False
        assert limiter.allow("user2") is False

    def test_refill_over_time(self):
        limiter = _UserRateLimiter(max_tokens=1, refill_per_second=100)
        assert limiter.allow("user1") is True
        assert limiter.allow("user1") is False
        time.sleep(0.05)  # Allow refill (100/s × 0.05s = 5 tokens, capped at 1)
        assert limiter.allow("user1") is True

    def test_cleanup_idle_users(self):
        limiter = _UserRateLimiter(max_tokens=5)
        limiter.allow("user1")
        limiter.allow("user2")
        # Force old timestamp
        limiter._last_refill["user1"] = time.time() - 7200
        limiter.cleanup(max_idle_seconds=3600)
        assert "user1" not in limiter._buckets
        assert "user2" in limiter._buckets

    def test_thread_safety(self):
        limiter = _UserRateLimiter(max_tokens=50, refill_per_second=0)
        results = []
        results_lock = threading.Lock()

        def worker():
            for _ in range(20):
                r = limiter.allow("shared_user")
                with results_lock:
                    results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 50 should be True (max_tokens=50, no refill)
        assert sum(results) == 50
        assert len(results) == 100


# ---------------------------------------------------------------------------
# Thread-safe dedup tests
# ---------------------------------------------------------------------------

class TestThreadSafeDedup:
    def test_dedup_blocks_duplicate(self):
        handler = FeishuBotHandler()
        assert handler._is_duplicate("msg1") is False
        assert handler._is_duplicate("msg1") is True

    def test_dedup_empty_id_not_blocked(self):
        handler = FeishuBotHandler()
        assert handler._is_duplicate("") is False
        assert handler._is_duplicate("") is False

    def test_dedup_different_ids_allowed(self):
        handler = FeishuBotHandler()
        assert handler._is_duplicate("msg1") is False
        assert handler._is_duplicate("msg2") is False

    def test_dedup_thread_safety(self):
        handler = FeishuBotHandler()
        results = {"duplicates": 0, "unique": 0}
        lock = threading.Lock()

        def worker(msg_id):
            is_dup = handler._is_duplicate(msg_id)
            with lock:
                if is_dup:
                    results["duplicates"] += 1
                else:
                    results["unique"] += 1

        # 10 threads all try the same msg_id
        threads = [threading.Thread(target=worker, args=("same_msg",)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 1 should be unique, 9 duplicates
        assert results["unique"] == 1
        assert results["duplicates"] == 9

    def test_dedup_cleanup_at_capacity(self):
        handler = FeishuBotHandler()
        # Fill up to trigger cleanup
        for i in range(5001):
            handler._is_duplicate(f"msg_{i}")
        # After cleanup, set should be bounded
        assert len(handler._processed_msg_ids) <= 2500


# ---------------------------------------------------------------------------
# User role mapping tests
# ---------------------------------------------------------------------------

class TestUserRoleMapping:
    def test_default_role(self):
        handler = FeishuBotHandler()
        assert handler.get_user_role("unknown_user") == "operator"

    def test_custom_role_mapping(self):
        handler = FeishuBotHandler(user_roles={
            "uid_admin": "admin",
            "uid_researcher": "researcher",
        })
        assert handler.get_user_role("uid_admin") == "admin"
        assert handler.get_user_role("uid_researcher") == "researcher"
        assert handler.get_user_role("uid_other") == "operator"

    def test_set_role_dynamically(self):
        handler = FeishuBotHandler()
        handler.set_user_role("uid_new", "teacher")
        assert handler.get_user_role("uid_new") == "teacher"


# ---------------------------------------------------------------------------
# Active user tracking tests
# ---------------------------------------------------------------------------

class TestActiveUserTracking:
    def test_track_user(self):
        handler = FeishuBotHandler()
        handler._track_user("user1")
        handler._track_user("user2")
        active = handler.get_active_users()
        assert "user1" in active
        assert "user2" in active

    def test_active_user_count(self):
        handler = FeishuBotHandler()
        handler._track_user("user1")
        handler._track_user("user2")
        assert handler.get_active_user_count() == 2

    def test_active_user_count_excludes_old(self):
        handler = FeishuBotHandler()
        handler._track_user("user1")
        # Simulate user2 was active 2 hours ago
        with handler._active_users_lock:
            handler._active_users["user2"] = time.time() - 7200
        assert handler.get_active_user_count() == 1


# ---------------------------------------------------------------------------
# Sync handle_message tests (multi-user)
# ---------------------------------------------------------------------------

class TestSyncMultiUser:
    @pytest.mark.asyncio
    async def test_multiple_users_sequential(self):
        orch = ConcurrentMockOrchestrator()
        handler = FeishuBotHandler(orchestrator=orch)

        for i in range(5):
            msg = FeishuMessage(
                msg_id=f"msg_{i}",
                text=f"Hello from user {i}",
                user_id=f"user_{i}",
            )
            resp = await handler.handle_message(msg)
            assert resp.status == "success"

        assert len(orch.requests) == 5
        # Each request should have different user_id
        user_ids = {r["user_id"] for r in orch.requests}
        assert len(user_ids) == 5

    @pytest.mark.asyncio
    async def test_rate_limited_user(self):
        handler = FeishuBotHandler(
            orchestrator=ConcurrentMockOrchestrator(),
            rate_limit=2,
        )

        results = []
        for i in range(4):
            msg = FeishuMessage(
                msg_id=f"msg_{i}",
                text="test",
                user_id="same_user",
            )
            resp = await handler.handle_message(msg)
            results.append(resp.status)

        # First 2 should succeed, rest rate limited
        assert results[0] == "success"
        assert results[1] == "success"
        assert results[2] == "warning"  # rate limited

    @pytest.mark.asyncio
    async def test_user_role_passed_to_orchestrator(self):
        orch = ConcurrentMockOrchestrator()
        handler = FeishuBotHandler(
            orchestrator=orch,
            user_roles={"uid_admin": "admin"},
        )

        msg = FeishuMessage(msg_id="m1", text="test", user_id="uid_admin")
        await handler.handle_message(msg)

        assert orch.requests[0]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_session_id_contains_user_id(self):
        orch = ConcurrentMockOrchestrator()
        handler = FeishuBotHandler(orchestrator=orch)

        msg = FeishuMessage(msg_id="m1", text="test", user_id="uid_42")
        await handler.handle_message(msg)

        assert orch.requests[0]["session_id"] == "feishu:uid_42"

    @pytest.mark.asyncio
    async def test_help_command(self):
        handler = FeishuBotHandler(orchestrator=ConcurrentMockOrchestrator())
        msg = FeishuMessage(msg_id="m1", text="/帮助", user_id="u1")
        resp = await handler.handle_message(msg)
        assert resp.status == "info"
        assert "可用命令" in resp.content

    @pytest.mark.asyncio
    async def test_help_command_english(self):
        handler = FeishuBotHandler(orchestrator=ConcurrentMockOrchestrator())
        msg = FeishuMessage(msg_id="m2", text="/help", user_id="u1")
        resp = await handler.handle_message(msg)
        assert "Available Commands" in resp.content


# ---------------------------------------------------------------------------
# Async handle_message_async tests
# ---------------------------------------------------------------------------

class TestAsyncBackgroundProcessing:
    def test_async_returns_accepted(self):
        orch = ConcurrentMockOrchestrator()
        handler = FeishuBotHandler(orchestrator=orch)

        loop = asyncio.new_event_loop()
        msg = FeishuMessage(msg_id="am1", text="test", user_id="u1")
        ack = handler.handle_message_async(msg, loop=loop)
        assert ack["status"] == "accepted"
        assert ack["user_id"] == "u1"

        # Run pending tasks
        loop.run_until_complete(asyncio.sleep(0.1))
        loop.close()

    def test_async_dedup(self):
        handler = FeishuBotHandler(orchestrator=ConcurrentMockOrchestrator())
        loop = asyncio.new_event_loop()

        msg = FeishuMessage(msg_id="dup1", text="test", user_id="u1")
        ack1 = handler.handle_message_async(msg, loop=loop)
        ack2 = handler.handle_message_async(msg, loop=loop)

        assert ack1["status"] == "accepted"
        assert ack2["status"] == "duplicate"

        loop.run_until_complete(asyncio.sleep(0.1))
        loop.close()

    def test_async_rate_limited(self):
        handler = FeishuBotHandler(
            orchestrator=ConcurrentMockOrchestrator(),
            rate_limit=1,
        )
        loop = asyncio.new_event_loop()

        ack1 = handler.handle_message_async(
            FeishuMessage(msg_id="r1", text="a", user_id="u1"), loop=loop,
        )
        ack2 = handler.handle_message_async(
            FeishuMessage(msg_id="r2", text="b", user_id="u1"), loop=loop,
        )

        assert ack1["status"] == "accepted"
        assert ack2["status"] == "rate_limited"

        loop.run_until_complete(asyncio.sleep(0.1))
        loop.close()


# ---------------------------------------------------------------------------
# Concurrent async processing tests
# ---------------------------------------------------------------------------

class TestConcurrentProcessing:
    @pytest.mark.asyncio
    async def test_concurrent_users_all_processed(self):
        orch = ConcurrentMockOrchestrator(delay=0.01)
        handler = FeishuBotHandler(orchestrator=orch, rate_limit=20)

        # Launch 10 concurrent users
        tasks = []
        for i in range(10):
            msg = FeishuMessage(
                msg_id=f"conc_{i}",
                text=f"Message from user {i}",
                user_id=f"user_{i}",
            )
            tasks.append(handler.handle_message(msg))

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status == "success" for r in results)
        assert len(orch.requests) == 10

        # All different users
        user_ids = {r["user_id"] for r in orch.requests}
        assert len(user_ids) == 10

    @pytest.mark.asyncio
    async def test_concurrent_same_user_rate_limited(self):
        orch = ConcurrentMockOrchestrator()
        handler = FeishuBotHandler(orchestrator=orch, rate_limit=3)

        tasks = []
        for i in range(6):
            msg = FeishuMessage(
                msg_id=f"rl_{i}",
                text=f"msg {i}",
                user_id="same_user",
            )
            tasks.append(handler.handle_message(msg))

        results = await asyncio.gather(*tasks)
        statuses = [r.status for r in results]

        success_count = statuses.count("success")
        warning_count = statuses.count("warning")

        # At most 3 should succeed (rate limit)
        assert success_count <= 3
        assert warning_count >= 3


# ---------------------------------------------------------------------------
# Webhook router tests (with TestClient)
# ---------------------------------------------------------------------------

class TestWebhookRouter:
    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_webhook_challenge(self, client):
        resp = client.post("/api/feishu/webhook", json={
            "raw_body": {"challenge": "test_challenge_123"},
        })
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "test_challenge_123"

    def test_webhook_empty_text_ignored(self, client):
        resp = client.post("/api/feishu/webhook", json={
            "raw_body": {
                "event": {
                    "message": {
                        "message_id": "empty_1",
                        "message_type": "text",
                        "content": '{"text": ""}',
                    },
                    "sender": {"sender_id": {"user_id": "u1"}},
                },
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("ignored", "accepted")

    def test_webhook_image_ignored(self, client):
        resp = client.post("/api/feishu/webhook", json={
            "raw_body": {
                "event": {
                    "message": {
                        "message_id": "img_1",
                        "message_type": "image",
                        "content": "",
                    },
                    "sender": {"sender_id": {"user_id": "u1"}},
                },
            },
        })
        assert resp.status_code == 200

    def test_active_users_endpoint(self, client):
        resp = client.get("/api/feishu/users")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_users" in data
        assert "total" in data

    def test_set_user_role_valid(self, client):
        resp = client.post(
            "/api/feishu/users/role",
            params={"user_id": "test_uid", "role": "admin"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_set_user_role_invalid(self, client):
        resp = client.post(
            "/api/feishu/users/role",
            params={"user_id": "test_uid", "role": "invalid_role"},
        )
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_status_includes_active_users(self, client):
        resp = client.get("/api/feishu/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_users" in data["bot"]
