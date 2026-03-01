"""Personality system — SOUL.md / USER.md / IDENTITY.md management.
人格系统 — 管理 AI 助理的身份、人格和用户画像。

Inspired by OpenClaw's personality file mechanism:
- SOUL.md: Core identity and cognitive capabilities
- USER.md: Per-user/group profile and preferences
- IDENTITY.md: Agent name, emoji, vibe

These files ARE the memory — the system reads them at startup and updates them
to persist knowledge across sessions.
"""

from hydroclaw.personality.manager import PersonalityManager

__all__ = ["PersonalityManager"]
