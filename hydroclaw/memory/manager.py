"""MemoryManager — persistent knowledge and daily interaction notes.
记忆管理器 — 持久化知识沉淀和每日交互笔记。

Memory structure per group:
    data/memory/{group}/
    ├── MEMORY.md                 # Long-term refined knowledge
    └── daily/
        ├── 2026-03-01.md        # Daily interaction log
        ├── 2026-03-02.md
        └── ...
"""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "memory"


@dataclass
class MemoryEntry:
    """A single memory entry with relevance scoring."""
    content: str
    source: str  # "memory" | "daily" | "interaction"
    timestamp: datetime = field(default_factory=datetime.now)
    keywords: list[str] = field(default_factory=list)
    relevance: float = 0.0


class MemoryManager:
    """Manages long-term memory and daily notes per user group.

    Features:
    - MEMORY.md: Long-term curated knowledge (auto-maintained)
    - Daily notes: Raw interaction records per day
    - Keyword search with time-decay scoring
    - Memory consolidation (merge daily notes into MEMORY.md)
    """

    def __init__(self, memory_dir: str | Path | None = None):
        self._dir = Path(memory_dir or os.environ.get(
            "HYDROCLAW_MEMORY_DIR", _DEFAULT_MEMORY_DIR
        ))

    @property
    def memory_dir(self) -> Path:
        return self._dir

    def _group_dir(self, group: str) -> Path:
        d = self._dir / group
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---- Long-term memory (MEMORY.md) ----

    def get_memory(self, group: str = "default") -> str:
        """Read the long-term MEMORY.md for a group."""
        path = self._group_dir(group) / "MEMORY.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def append_memory(self, group: str, content: str) -> None:
        """Append a new entry to MEMORY.md."""
        path = self._group_dir(group) / "MEMORY.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n\n## [{timestamp}]\n{content}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    def update_memory(self, group: str, content: str) -> None:
        """Replace the entire MEMORY.md content."""
        path = self._group_dir(group) / "MEMORY.md"
        path.write_text(content, encoding="utf-8")

    # ---- Daily notes ----

    def get_daily_note(self, group: str, date: str | None = None) -> str:
        """Read the daily note for a specific date (default: today)."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        path = self._group_dir(group) / "daily" / f"{date}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def append_daily_note(
        self,
        group: str,
        content: str,
        user_id: str = "",
        date: str | None = None,
    ) -> None:
        """Append an entry to today's daily note."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        daily_dir = self._group_dir(group) / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        path = daily_dir / f"{date}.md"

        timestamp = datetime.now().strftime("%H:%M:%S")
        user_tag = f" [user:{user_id}]" if user_id else ""
        entry = f"\n### {timestamp}{user_tag}\n{content}\n"

        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    def list_daily_notes(self, group: str, limit: int = 30) -> list[str]:
        """List available daily note dates (newest first)."""
        daily_dir = self._group_dir(group) / "daily"
        if not daily_dir.exists():
            return []
        dates = sorted(
            (f.stem for f in daily_dir.glob("*.md")),
            reverse=True,
        )
        return dates[:limit]

    # ---- Search ----

    def search(
        self,
        group: str,
        query: str,
        max_results: int = 10,
        decay_days: float = 30.0,
    ) -> list[MemoryEntry]:
        """Search memory and daily notes with keyword matching + time decay.

        Scoring: keyword_hits / total_keywords * time_decay_factor
        Time decay: exp(-days_ago / decay_days)
        """
        keywords = _extract_keywords(query)
        if not keywords:
            return []

        results: list[MemoryEntry] = []

        # Search MEMORY.md
        memory_text = self.get_memory(group)
        if memory_text:
            for section in _split_sections(memory_text):
                score = _keyword_score(section, keywords)
                if score > 0:
                    results.append(MemoryEntry(
                        content=section,
                        source="memory",
                        relevance=score,
                    ))

        # Search daily notes (recent first)
        now = datetime.now()
        for date_str in self.list_daily_notes(group, limit=60):
            try:
                note_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            days_ago = (now - note_date).days
            decay = math.exp(-days_ago / decay_days)

            note_text = self.get_daily_note(group, date_str)
            for section in _split_sections(note_text):
                score = _keyword_score(section, keywords) * decay
                if score > 0:
                    results.append(MemoryEntry(
                        content=section,
                        source="daily",
                        timestamp=note_date,
                        relevance=score,
                    ))

        # Sort by relevance, return top N
        results.sort(key=lambda e: e.relevance, reverse=True)
        return results[:max_results]

    # ---- Consolidation ----

    def consolidate(self, group: str, days_back: int = 7) -> str:
        """Consolidate recent daily notes into a summary.

        Returns the summary text (caller decides whether to append to MEMORY.md).
        """
        notes = []
        for date_str in self.list_daily_notes(group, limit=days_back):
            content = self.get_daily_note(group, date_str)
            if content.strip():
                notes.append(f"## {date_str}\n{content}")

        if not notes:
            return ""

        # Simple consolidation: combine and return for manual review
        return "\n\n---\n\n".join(notes)


# ---- Internal helpers ----

def _extract_keywords(text: str) -> list[str]:
    """Extract keywords from text for simple matching."""
    # Remove punctuation, split into words
    clean = re.sub(r'[^\w\s]', ' ', text)
    words = clean.split()
    # Filter out short words and common stop words
    stop_words = {"的", "了", "在", "是", "和", "与", "对", "为", "a", "the", "is", "in", "to", "and"}
    return [w.lower() for w in words if len(w) >= 2 and w.lower() not in stop_words]


def _keyword_score(text: str, keywords: list[str]) -> float:
    """Score text against keywords (0.0 - 1.0)."""
    if not keywords:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw in text_lower)
    return hits / len(keywords)


def _split_sections(text: str) -> list[str]:
    """Split markdown text into sections by headers."""
    sections = re.split(r'\n(?=##?\s)', text)
    return [s.strip() for s in sections if s.strip()]
