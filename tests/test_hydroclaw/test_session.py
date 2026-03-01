"""Tests for HydroClaw session management.
HydroClaw 会话管理测试。
"""

import pytest

from hydroclaw.session.manager import SessionManager, Session, ConversationTurn


class TestConversationTurn:
    """Test ConversationTurn dataclass."""

    def test_to_dict(self):
        turn = ConversationTurn(role="user", content="你好")
        d = turn.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "你好"
        assert "timestamp" in d

    def test_metadata(self):
        turn = ConversationTurn(
            role="assistant", content="回复",
            metadata={"skill": "forecast"},
        )
        assert turn.metadata["skill"] == "forecast"


class TestSession:
    """Test Session dataclass."""

    def test_add_turn(self):
        session = Session(session_id="test", user_id="u1")
        session.add_turn("user", "水平衡怎么样？")
        session.add_turn("assistant", "节点A残差正常。")
        assert len(session.history) == 2

    def test_history_limit(self):
        session = Session(session_id="test", user_id="u1")
        for i in range(100):
            session.add_turn("user", f"Message {i}")
        # Should be trimmed to MAX_HISTORY (50)
        assert len(session.history) == 50

    def test_get_context_messages(self):
        session = Session(session_id="test", user_id="u1")
        for i in range(20):
            session.add_turn("user", f"Q{i}")
        messages = session.get_context_messages(limit=5)
        assert len(messages) == 5
        assert messages[-1]["content"] == "Q19"

    def test_to_dict(self):
        session = Session(session_id="s1", user_id="u1", group="admin")
        d = session.to_dict()
        assert d["session_id"] == "s1"
        assert d["user_id"] == "u1"
        assert d["group"] == "admin"


class TestSessionManager:
    """Test SessionManager."""

    def test_create_session(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path)
        session = mgr.get_or_create("user1")
        assert session.user_id == "user1"
        assert session.session_id == "default:api:user1"

    def test_get_existing_session(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path)
        s1 = mgr.get_or_create("user1")
        s1.add_turn("user", "Hello")
        s2 = mgr.get_or_create("user1")
        assert s2 is s1
        assert len(s2.history) == 1

    def test_per_user_isolation(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path, scope="per-user")
        s1 = mgr.get_or_create("user1")
        s2 = mgr.get_or_create("user2")
        s1.add_turn("user", "User 1 message")
        assert len(s2.history) == 0  # Isolated

    def test_per_group_scope(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path, scope="per-group")
        s1 = mgr.get_or_create("user1", group="admin")
        s2 = mgr.get_or_create("user2", group="admin")
        # Same group, same session
        assert s1 is s2

    def test_main_scope(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path, scope="main")
        s1 = mgr.get_or_create("user1")
        s2 = mgr.get_or_create("user2")
        assert s1 is s2  # Main scope: all share one session

    def test_save_and_load(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path)
        session = mgr.get_or_create("user1")
        session.add_turn("user", "水平衡查询")
        session.add_turn("assistant", "正常")
        mgr.save_session(session)

        # Create new manager (fresh cache)
        mgr2 = SessionManager(session_dir=tmp_path)
        loaded = mgr2.get_or_create("user1")
        assert len(loaded.history) == 2
        assert loaded.history[0].content == "水平衡查询"

    def test_session_count(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path)
        mgr.get_or_create("user1")
        mgr.get_or_create("user2")
        mgr.get_or_create("user3")
        assert mgr.get_session_count() == 3

    def test_get_active_sessions(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path)
        mgr.get_or_create("user1", group="admin")
        mgr.get_or_create("user2", group="student")
        mgr.get_or_create("user3", group="admin")

        admin_sessions = mgr.get_active_sessions(group="admin")
        assert len(admin_sessions) == 2

    def test_cleanup_stale(self, tmp_path):
        import time
        mgr = SessionManager(session_dir=tmp_path)
        session = mgr.get_or_create("old_user")
        session.last_active = time.time() - 100000  # Very old
        mgr.get_or_create("new_user")

        removed = mgr.cleanup_stale(max_idle_hours=1)
        assert removed == 1
        assert mgr.get_session_count() == 1

    def test_evict_oldest(self, tmp_path):
        mgr = SessionManager(session_dir=tmp_path, max_sessions=3)
        mgr.get_or_create("user1")
        mgr.get_or_create("user2")
        mgr.get_or_create("user3")
        mgr.get_or_create("user4")  # Should evict user1
        assert mgr.get_session_count() == 3
