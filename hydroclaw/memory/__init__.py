"""Memory system — long-term knowledge, daily notes, interaction logs.
记忆系统 — 长期知识沉淀、每日笔记、交互日志。

Inspired by OpenClaw's memory mechanism:
- MEMORY.md: Long-term refined knowledge (agent self-maintains)
- memory/YYYY-MM-DD.md: Daily interaction notes
- Hybrid search: keyword + time-decay scoring
"""

from hydroclaw.memory.manager import MemoryManager

__all__ = ["MemoryManager"]
