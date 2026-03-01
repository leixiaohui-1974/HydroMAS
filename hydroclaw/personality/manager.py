"""PersonalityManager — load, query, and update SOUL/USER/IDENTITY files.
人格管理器 — 加载、查询和更新 SOUL/USER/IDENTITY 文件。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PERSONALITY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "personality"


@dataclass
class PersonalityProfile:
    """Loaded personality profile combining SOUL + USER + IDENTITY."""
    soul: str = ""
    user: str = ""
    identity: str = ""
    role: str = "operator"
    group: str = "default"
    metadata: dict = field(default_factory=dict)

    @property
    def agent_name(self) -> str:
        """Extract agent name from IDENTITY or default."""
        for line in self.identity.splitlines():
            if line.startswith("name:") or line.startswith("**Name:**"):
                return line.split(":", 1)[1].strip().strip("*").strip()
        return "小瀚"

    @property
    def agent_emoji(self) -> str:
        for line in self.identity.splitlines():
            if "emoji" in line.lower():
                parts = line.split(":", 1)
                if len(parts) > 1:
                    return parts[1].strip()
        return "🌊"

    def get_system_prompt(self) -> str:
        """Build a system prompt from personality files."""
        parts = []
        if self.soul:
            parts.append(self.soul)
        if self.identity:
            parts.append(f"\n---\n{self.identity}")
        if self.user:
            parts.append(f"\n---\n用户画像:\n{self.user}")
        return "\n".join(parts)


class PersonalityManager:
    """Manages personality files for different user groups.

    Directory structure:
        data/personality/
        ├── SOUL.md              # Shared soul (all groups)
        ├── IDENTITY.md          # Shared identity
        ├── groups/
        │   ├── admin/
        │   │   └── USER.md      # Admin group profile
        │   ├── student-a/
        │   │   └── USER.md      # Student group A profile
        │   ├── student-b/
        │   │   └── USER.md
        │   ├── peer/
        │   │   └── USER.md      # IAHR peer group
        │   └── dev/
        │       └── USER.md      # Development group
        └── users/
            └── {user_id}.md     # Per-user overrides (optional)
    """

    def __init__(self, personality_dir: str | Path | None = None):
        self._dir = Path(personality_dir or os.environ.get(
            "HYDROCLAW_PERSONALITY_DIR", _DEFAULT_PERSONALITY_DIR
        ))
        self._cache: dict[str, PersonalityProfile] = {}

    @property
    def personality_dir(self) -> Path:
        return self._dir

    def _read_file(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def load_profile(
        self,
        group: str = "default",
        user_id: str = "",
        role: str = "operator",
    ) -> PersonalityProfile:
        """Load personality profile for a group/user combination.

        Priority: user-specific > group > shared defaults.
        """
        cache_key = f"{group}:{user_id}:{role}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Shared files
        soul = self._read_file(self._dir / "SOUL.md")
        identity = self._read_file(self._dir / "IDENTITY.md")

        # Group-specific USER.md
        user_content = self._read_file(self._dir / "groups" / group / "USER.md")

        # Per-user override (if exists)
        if user_id:
            user_override = self._read_file(self._dir / "users" / f"{user_id}.md")
            if user_override:
                user_content = user_override

        profile = PersonalityProfile(
            soul=soul,
            user=user_content,
            identity=identity,
            role=role,
            group=group,
        )
        self._cache[cache_key] = profile
        return profile

    def get_all_groups(self) -> list[str]:
        """List all configured groups."""
        groups_dir = self._dir / "groups"
        if not groups_dir.exists():
            return []
        return sorted(
            d.name for d in groups_dir.iterdir() if d.is_dir()
        )

    def update_user_profile(self, user_id: str, content: str) -> None:
        """Update or create a per-user profile."""
        users_dir = self._dir / "users"
        users_dir.mkdir(parents=True, exist_ok=True)
        (users_dir / f"{user_id}.md").write_text(content, encoding="utf-8")
        # Invalidate cache entries for this user
        keys_to_remove = [k for k in self._cache if f":{user_id}:" in k]
        for k in keys_to_remove:
            del self._cache[k]

    def clear_cache(self) -> None:
        self._cache.clear()
