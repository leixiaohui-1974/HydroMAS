"""SessionManager — multi-user session isolation and persistence.
会话管理器 — 多用户会话隔离与持久化。

Inspired by OpenClaw's session management:
- dmScope=per-channel-peer: Each user gets isolated conversation context
- Session key: "{group}:{channel}:{user_id}"
- Conversation history persisted as JSONL

Supports three scoping modes:
- "per-user": Full isolation per user (recommended for production)
- "per-group": Shared within group (for teaching scenarios)
- "main": All share one session (dev/debug only)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SESSION_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"
_MAX_HISTORY = 50  # Max conversation turns per session


@dataclass
class ConversationTurn:
    """A single turn in conversation history."""
    role: str  # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Session:
    """An isolated user session with conversation history and state."""
    session_id: str
    user_id: str
    group: str = "default"
    channel: str = "api"  # "api" | "feishu" | "web"
    role: str = "operator"
    history: list[ConversationTurn] = field(default_factory=list)
    state: dict = field(default_factory=dict)  # Session-scoped state
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str, metadata: dict | None = None) -> None:
        """Add a conversation turn, trimming old history if needed."""
        self.history.append(ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {},
        ))
        self.last_active = time.time()
        # Keep only recent history
        if len(self.history) > _MAX_HISTORY:
            self.history = self.history[-_MAX_HISTORY:]

    def get_context_messages(self, limit: int = 10) -> list[dict]:
        """Get recent conversation for LLM context."""
        return [t.to_dict() for t in self.history[-limit:]]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "group": self.group,
            "channel": self.channel,
            "role": self.role,
            "history_length": len(self.history),
            "created_at": self.created_at,
            "last_active": self.last_active,
            "state": self.state,
        }


class SessionManager:
    """Manages user sessions with configurable isolation scope.

    Session key format: "{group}:{channel}:{user_id}"
    """

    def __init__(
        self,
        session_dir: str | Path | None = None,
        scope: str = "per-user",
        max_sessions: int = 1000,
    ):
        self._dir = Path(session_dir or os.environ.get(
            "HYDROCLAW_SESSION_DIR", _DEFAULT_SESSION_DIR
        ))
        self._scope = scope  # "per-user" | "per-group" | "main"
        self._max_sessions = max_sessions
        self._sessions: dict[str, Session] = {}

    @property
    def scope(self) -> str:
        return self._scope

    def _make_key(self, user_id: str, group: str, channel: str) -> str:
        """Generate session key based on scope."""
        if self._scope == "main":
            return "main"
        elif self._scope == "per-group":
            return f"{group}:{channel}"
        else:  # per-user (default)
            return f"{group}:{channel}:{user_id}"

    def get_or_create(
        self,
        user_id: str,
        group: str = "default",
        channel: str = "api",
        role: str = "operator",
    ) -> Session:
        """Get existing session or create a new one."""
        key = self._make_key(user_id, group, channel)

        if key in self._sessions:
            session = self._sessions[key]
            session.last_active = time.time()
            return session

        # Try loading from disk
        session = self._load_session(key)
        if session:
            self._sessions[key] = session
            return session

        # Create new session
        session = Session(
            session_id=key,
            user_id=user_id,
            group=group,
            channel=channel,
            role=role,
        )
        self._sessions[key] = session

        # Evict oldest if over limit
        if len(self._sessions) > self._max_sessions:
            self._evict_oldest()

        return session

    def save_session(self, session: Session) -> None:
        """Persist session to disk."""
        self._dir.mkdir(parents=True, exist_ok=True)
        safe_name = session.session_id.replace(":", "_").replace("/", "_")
        path = self._dir / f"{safe_name}.jsonl"

        with open(path, "w", encoding="utf-8") as f:
            # Write session metadata
            meta = {
                "_type": "session_meta",
                "session_id": session.session_id,
                "user_id": session.user_id,
                "group": session.group,
                "channel": session.channel,
                "role": session.role,
                "created_at": session.created_at,
                "last_active": session.last_active,
                "state": session.state,
            }
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")

            # Write conversation turns
            for turn in session.history:
                f.write(json.dumps(turn.to_dict(), ensure_ascii=False) + "\n")

    def _load_session(self, key: str) -> Session | None:
        """Load session from disk."""
        safe_name = key.replace(":", "_").replace("/", "_")
        path = self._dir / f"{safe_name}.jsonl"
        if not path.exists():
            return None

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            if not lines:
                return None

            meta = json.loads(lines[0])
            if meta.get("_type") != "session_meta":
                return None

            session = Session(
                session_id=meta["session_id"],
                user_id=meta.get("user_id", ""),
                group=meta.get("group", "default"),
                channel=meta.get("channel", "api"),
                role=meta.get("role", "operator"),
                created_at=meta.get("created_at", time.time()),
                last_active=meta.get("last_active", time.time()),
                state=meta.get("state", {}),
            )

            for line in lines[1:]:
                data = json.loads(line)
                session.history.append(ConversationTurn(
                    role=data["role"],
                    content=data["content"],
                    timestamp=data.get("timestamp", 0),
                    metadata=data.get("metadata", {}),
                ))

            return session
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to load session from %s", path)
            return None

    def _evict_oldest(self) -> None:
        """Remove the oldest session to stay under limit."""
        if not self._sessions:
            return
        oldest_key = min(self._sessions, key=lambda k: self._sessions[k].last_active)
        del self._sessions[oldest_key]

    def get_active_sessions(self, group: str | None = None) -> list[Session]:
        """List active sessions, optionally filtered by group."""
        sessions = list(self._sessions.values())
        if group:
            sessions = [s for s in sessions if s.group == group]
        sessions.sort(key=lambda s: s.last_active, reverse=True)
        return sessions

    def get_session_count(self) -> int:
        return len(self._sessions)

    def cleanup_stale(self, max_idle_hours: float = 24.0) -> int:
        """Remove sessions idle for more than max_idle_hours."""
        cutoff = time.time() - max_idle_hours * 3600
        stale_keys = [
            k for k, s in self._sessions.items()
            if s.last_active < cutoff
        ]
        for key in stale_keys:
            del self._sessions[key]
        return len(stale_keys)
