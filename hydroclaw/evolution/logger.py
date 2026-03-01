"""InteractionLogger — JSONL logging of all user-system interactions.
交互日志记录器 — 以 JSONL 格式记录所有用户-系统交互。

每条交互日志包含:
- timestamp: 时间戳
- user_id: 用户标识
- channel: 通道 (api/feishu/web)
- intent: 识别的意图
- skill_used: 使用的技能
- success: 是否成功
- response_time_ms: 响应时间
- error: 错误信息 (如有)
- user_feedback: 用户反馈 (如有)

This data feeds the self-evolution pipeline:
  evolve_auto.sh → 分析日志 → 识别需求 → Claude Code 开发 → 测试 → 部署
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "interactions"


@dataclass
class InteractionRecord:
    """A single interaction record for evolution analysis."""
    timestamp: float = field(default_factory=time.time)
    user_id: str = ""
    group: str = "default"
    channel: str = "api"
    role: str = "operator"
    message: str = ""
    intent_type: str = ""
    intent_target: str = ""
    intent_confidence: float = 0.0
    skill_used: str = ""
    success: bool = True
    response_time_ms: float = 0.0
    error: str = ""
    result_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "group": self.group,
            "channel": self.channel,
            "role": self.role,
            "message": self.message,
            "intent_type": self.intent_type,
            "intent_target": self.intent_target,
            "intent_confidence": self.intent_confidence,
            "skill_used": self.skill_used,
            "success": self.success,
            "response_time_ms": self.response_time_ms,
            "error": self.error,
            "result_summary": self.result_summary,
        }


class InteractionLogger:
    """Logs all interactions to JSONL files for self-evolution analysis.

    File naming: interactions_YYYY-MM-DD.jsonl
    One file per day, append-only.
    """

    def __init__(self, log_dir: str | Path | None = None):
        self._dir = Path(log_dir or os.environ.get(
            "HYDROCLAW_INTERACTION_DIR", _DEFAULT_LOG_DIR
        ))
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def log_dir(self) -> Path:
        return self._dir

    def _get_today_file(self) -> Path:
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self._dir / f"interactions_{date_str}.jsonl"

    def log(self, record: InteractionRecord) -> None:
        """Append an interaction record to today's log file."""
        path = self._get_today_file()
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write interaction log")

    def log_chat(
        self,
        message: str,
        user_id: str = "",
        group: str = "default",
        channel: str = "api",
        role: str = "operator",
        intent_type: str = "",
        intent_target: str = "",
        intent_confidence: float = 0.0,
        skill_used: str = "",
        success: bool = True,
        response_time_ms: float = 0.0,
        error: str = "",
        result_summary: str = "",
    ) -> None:
        """Convenience method to log a chat interaction."""
        self.log(InteractionRecord(
            user_id=user_id,
            group=group,
            channel=channel,
            role=role,
            message=message,
            intent_type=intent_type,
            intent_target=intent_target,
            intent_confidence=intent_confidence,
            skill_used=skill_used,
            success=success,
            response_time_ms=response_time_ms,
            error=error,
            result_summary=result_summary,
        ))

    def get_records(
        self,
        date: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Read interaction records, optionally filtered."""
        from datetime import datetime

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        path = self._dir / f"interactions_{date}.jsonl"
        if not path.exists():
            return []

        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if user_id and rec.get("user_id") != user_id:
                    continue
                records.append(rec)
            except json.JSONDecodeError:
                continue

        records.reverse()  # Newest first
        return records[:limit]

    def get_available_dates(self, limit: int = 30) -> list[str]:
        """List available log dates (newest first)."""
        files = sorted(self._dir.glob("interactions_*.jsonl"), reverse=True)
        dates = []
        for f in files[:limit]:
            # Extract date from filename
            name = f.stem  # "interactions_2026-03-01"
            if name.startswith("interactions_"):
                dates.append(name[len("interactions_"):])
        return dates

    def get_stats(self, date: str | None = None) -> dict:
        """Get interaction statistics for a given date."""
        records = self.get_records(date=date, limit=10000)
        if not records:
            return {"total": 0, "date": date}

        total = len(records)
        success_count = sum(1 for r in records if r.get("success", True))
        unique_users = len(set(r.get("user_id", "") for r in records if r.get("user_id")))
        avg_response = (
            sum(r.get("response_time_ms", 0) for r in records) / total
            if total > 0 else 0
        )

        # Count by intent type
        intent_counts: dict[str, int] = {}
        for r in records:
            it = r.get("intent_type", "unknown")
            intent_counts[it] = intent_counts.get(it, 0) + 1

        # Count by skill
        skill_counts: dict[str, int] = {}
        for r in records:
            sk = r.get("skill_used", "")
            if sk:
                skill_counts[sk] = skill_counts.get(sk, 0) + 1

        # Error analysis
        errors = [r.get("error", "") for r in records if r.get("error")]

        return {
            "date": date,
            "total": total,
            "success_count": success_count,
            "success_rate": round(success_count / total * 100, 1) if total > 0 else 0,
            "unique_users": unique_users,
            "avg_response_ms": round(avg_response, 1),
            "intent_distribution": intent_counts,
            "skill_usage": skill_counts,
            "error_count": len(errors),
            "sample_errors": errors[:5],
        }
