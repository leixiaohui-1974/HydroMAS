"""EvolutionAnalyzer — analyze interaction patterns to guide self-improvement.
自进化分析器 — 分析交互模式以指导自动改进。

Analysis dimensions:
1. Failed requests → which skills need fixing?
2. Repeated questions → what knowledge should be pre-loaded?
3. Response times → which paths need optimization?
4. User patterns → what features are users asking for?
5. Skill coverage → are there unmet capabilities?

Output: A structured improvement plan that can be processed by Claude Code.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ImprovementItem:
    """A single improvement suggestion."""
    category: str  # "bug_fix" | "new_feature" | "performance" | "knowledge"
    priority: str  # "high" | "medium" | "low"
    title: str
    description: str
    evidence: list[str] = field(default_factory=list)
    affected_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "affected_skills": self.affected_skills,
        }


@dataclass
class EvolutionReport:
    """Self-evolution analysis report."""
    analysis_date: str
    period_start: str
    period_end: str
    total_interactions: int = 0
    unique_users: int = 0
    success_rate: float = 0.0
    improvements: list[ImprovementItem] = field(default_factory=list)
    statistics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "analysis_date": self.analysis_date,
            "period": {"start": self.period_start, "end": self.period_end},
            "total_interactions": self.total_interactions,
            "unique_users": self.unique_users,
            "success_rate": self.success_rate,
            "improvements": [i.to_dict() for i in self.improvements],
            "statistics": self.statistics,
        }

    def to_markdown(self) -> str:
        """Generate markdown report for Claude Code consumption."""
        lines = [
            f"# 自进化分析报告 — {self.analysis_date}",
            f"\n分析周期: {self.period_start} ~ {self.period_end}",
            f"\n## 概况",
            f"- 总交互数: {self.total_interactions}",
            f"- 独立用户: {self.unique_users}",
            f"- 成功率: {self.success_rate:.1f}%",
            f"\n## 改进建议 ({len(self.improvements)} 项)",
        ]

        for i, item in enumerate(self.improvements, 1):
            lines.append(f"\n### {i}. [{item.priority.upper()}] {item.title}")
            lines.append(f"- 类别: {item.category}")
            lines.append(f"- 描述: {item.description}")
            if item.affected_skills:
                lines.append(f"- 相关技能: {', '.join(item.affected_skills)}")
            if item.evidence:
                lines.append("- 证据:")
                for ev in item.evidence[:3]:
                    lines.append(f"  - {ev}")

        return "\n".join(lines)


class EvolutionAnalyzer:
    """Analyzes interaction logs to generate improvement plans.

    Data sources:
    - HydroMAS interaction logs (JSONL)
    - OpenClaw daily notes (if available)
    """

    def __init__(self, interaction_dir: str | Path | None = None):
        from hydroclaw.evolution.logger import _DEFAULT_LOG_DIR
        self._dir = Path(interaction_dir or _DEFAULT_LOG_DIR)

    def analyze(self, days_back: int = 7) -> EvolutionReport:
        """Analyze recent interactions and generate improvement report."""
        now = datetime.now()
        end_date = now.strftime("%Y-%m-%d")
        start_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")

        # Collect all records
        all_records = self._load_records(days_back)

        if not all_records:
            return EvolutionReport(
                analysis_date=end_date,
                period_start=start_date,
                period_end=end_date,
            )

        # Basic statistics
        total = len(all_records)
        success_count = sum(1 for r in all_records if r.get("success", True))
        unique_users = len(set(r.get("user_id", "") for r in all_records if r.get("user_id")))

        # Analyze patterns
        improvements = []
        improvements.extend(self._analyze_failures(all_records))
        improvements.extend(self._analyze_slow_responses(all_records))
        improvements.extend(self._analyze_repeated_queries(all_records))
        improvements.extend(self._analyze_skill_gaps(all_records))

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        improvements.sort(key=lambda x: priority_order.get(x.priority, 3))

        # Statistics
        intent_counts = Counter(r.get("intent_type", "unknown") for r in all_records)
        skill_counts = Counter(r.get("skill_used", "") for r in all_records if r.get("skill_used"))

        return EvolutionReport(
            analysis_date=end_date,
            period_start=start_date,
            period_end=end_date,
            total_interactions=total,
            unique_users=unique_users,
            success_rate=round(success_count / total * 100, 1) if total > 0 else 0,
            improvements=improvements,
            statistics={
                "intent_distribution": dict(intent_counts.most_common(20)),
                "skill_usage": dict(skill_counts.most_common(20)),
                "daily_volume": self._daily_volume(all_records),
            },
        )

    def _load_records(self, days_back: int) -> list[dict]:
        """Load interaction records for the specified period."""
        records = []
        now = datetime.now()
        for i in range(days_back):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            path = self._dir / f"interactions_{date}.jsonl"
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    def _analyze_failures(self, records: list[dict]) -> list[ImprovementItem]:
        """Identify skills with high failure rates."""
        items = []
        skill_results: dict[str, dict] = {}

        for r in records:
            skill = r.get("skill_used", "")
            if not skill:
                continue
            if skill not in skill_results:
                skill_results[skill] = {"success": 0, "fail": 0, "errors": []}
            if r.get("success", True):
                skill_results[skill]["success"] += 1
            else:
                skill_results[skill]["fail"] += 1
                if r.get("error"):
                    skill_results[skill]["errors"].append(r["error"])

        for skill, stats in skill_results.items():
            total = stats["success"] + stats["fail"]
            if total < 3:
                continue
            fail_rate = stats["fail"] / total
            if fail_rate > 0.3:
                items.append(ImprovementItem(
                    category="bug_fix",
                    priority="high" if fail_rate > 0.5 else "medium",
                    title=f"技能 '{skill}' 失败率过高 ({fail_rate:.0%})",
                    description=f"{total} 次调用中 {stats['fail']} 次失败",
                    evidence=stats["errors"][:3],
                    affected_skills=[skill],
                ))

        return items

    def _analyze_slow_responses(self, records: list[dict]) -> list[ImprovementItem]:
        """Identify slow response patterns."""
        items = []
        skill_times: dict[str, list[float]] = {}

        for r in records:
            skill = r.get("skill_used", "")
            rt = r.get("response_time_ms", 0)
            if skill and rt > 0:
                skill_times.setdefault(skill, []).append(rt)

        for skill, times in skill_times.items():
            if len(times) < 3:
                continue
            avg = sum(times) / len(times)
            if avg > 5000:  # > 5 seconds
                items.append(ImprovementItem(
                    category="performance",
                    priority="medium",
                    title=f"技能 '{skill}' 响应较慢 (平均 {avg:.0f}ms)",
                    description=f"建议优化计算路径或添加缓存",
                    affected_skills=[skill],
                ))

        return items

    def _analyze_repeated_queries(self, records: list[dict]) -> list[ImprovementItem]:
        """Identify frequently repeated queries (potential FAQ/cache candidates)."""
        items = []
        # Normalize messages for comparison
        msg_counts: Counter = Counter()
        for r in records:
            msg = r.get("message", "").strip().lower()
            if len(msg) > 5:
                msg_counts[msg] += 1

        for msg, count in msg_counts.most_common(5):
            if count >= 5:
                items.append(ImprovementItem(
                    category="knowledge",
                    priority="low",
                    title=f"高频问题: '{msg[:50]}...' ({count} 次)",
                    description="建议将答案预载入知识库或添加快捷操作",
                    evidence=[f"出现 {count} 次"],
                ))

        return items

    def _analyze_skill_gaps(self, records: list[dict]) -> list[ImprovementItem]:
        """Identify queries that couldn't be routed to any skill."""
        items = []
        unrouted = []
        for r in records:
            if not r.get("skill_used") and r.get("intent_type") in ("", "unknown", "fallback"):
                unrouted.append(r.get("message", ""))

        if len(unrouted) >= 5:
            items.append(ImprovementItem(
                category="new_feature",
                priority="medium",
                title=f"发现 {len(unrouted)} 条未匹配意图的请求",
                description="用户需求可能超出当前技能覆盖范围",
                evidence=unrouted[:5],
            ))

        return items

    def _daily_volume(self, records: list[dict]) -> dict[str, int]:
        """Count interactions per day."""
        daily: dict[str, int] = {}
        for r in records:
            ts = r.get("timestamp", 0)
            if ts:
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                daily[date] = daily.get(date, 0) + 1
        return daily

    def analyze_by_role(self, days_back: int = 7) -> dict[str, dict]:
        """Analyze interactions segmented by user role.

        Returns a dict keyed by role, each containing:
        - total, success_rate, avg_response_ms, top_skills, failure_skills
        """
        all_records = self._load_records(days_back)
        role_data: dict[str, list[dict]] = {}
        for r in all_records:
            role = r.get("role", "unknown")
            role_data.setdefault(role, []).append(r)

        result = {}
        for role, records in role_data.items():
            total = len(records)
            success = sum(1 for r in records if r.get("success", True))
            times = [r.get("response_time_ms", 0) for r in records if r.get("response_time_ms")]
            skills = Counter(r.get("skill_used", "") for r in records if r.get("skill_used"))
            fail_skills = Counter(
                r.get("skill_used", "") for r in records
                if r.get("skill_used") and not r.get("success", True)
            )
            result[role] = {
                "total": total,
                "success_rate": round(success / total * 100, 1) if total else 0,
                "avg_response_ms": round(sum(times) / len(times), 1) if times else 0,
                "top_skills": dict(skills.most_common(5)),
                "failure_skills": dict(fail_skills.most_common(5)),
            }
        return result

    def analyze_by_group(self, days_back: int = 7) -> dict[str, dict]:
        """Analyze interactions segmented by user group.

        Returns a dict keyed by group, each containing:
        - total, success_rate, unique_users, active_roles, top_skills
        """
        all_records = self._load_records(days_back)
        group_data: dict[str, list[dict]] = {}
        for r in all_records:
            group = r.get("group", "default")
            group_data.setdefault(group, []).append(r)

        result = {}
        for group, records in group_data.items():
            total = len(records)
            success = sum(1 for r in records if r.get("success", True))
            users = set(r.get("user_id", "") for r in records if r.get("user_id"))
            roles = set(r.get("role", "") for r in records if r.get("role"))
            skills = Counter(r.get("skill_used", "") for r in records if r.get("skill_used"))
            result[group] = {
                "total": total,
                "success_rate": round(success / total * 100, 1) if total else 0,
                "unique_users": len(users),
                "active_roles": sorted(roles),
                "top_skills": dict(skills.most_common(5)),
            }
        return result
