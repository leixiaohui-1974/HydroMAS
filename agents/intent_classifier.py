"""IntentClassifier — semantic multi-level intent classification.
意图分类器 — 语义多级意图分类。

Provides:
- TF-IDF keyword scoring for domain-specific intent recognition
- Multi-level routing: skill → tool → capability → planning
- Confidence calibration based on match depth
- Intent history tracking for adaptive routing
"""

from __future__ import annotations

import logging
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Result of intent classification. / 意图分类结果。"""

    route_type: str  # "skill" | "tool" | "capability" | "planning"
    target: str
    confidence: float
    domain: str = ""
    sub_intents: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "route_type": self.route_type,
            "target": self.target,
            "confidence": round(self.confidence, 3),
            "domain": self.domain,
            "sub_intents": self.sub_intents,
            "matched_keywords": self.matched_keywords,
            "metadata": self.metadata,
        }


# Domain categories for high-level classification
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "simulation": [
        "仿真", "模拟", "simulate", "simulation", "数字孪生", "digital twin",
        "管网仿真", "network simulation",
    ],
    "prediction": [
        "预测", "预报", "predict", "forecast", "趋势", "trend",
        "蒸发预测", "evaporation",
    ],
    "control": [
        "控制", "control", "PID", "MPC", "调节", "regulate",
    ],
    "safety": [
        "安全", "ODD", "safety", "边界", "boundary", "预警", "warning",
        "氧化铝ODD", "alumina ODD",
    ],
    "optimization": [
        "优化", "调度", "schedule", "dispatch", "设计", "design",
        "回用", "reuse", "全局调度",
    ],
    "diagnostics": [
        "诊断", "检测", "detect", "泄漏", "leak", "异常", "anomaly",
        "水平衡", "water balance", "残差",
    ],
    "reporting": [
        "报告", "report", "日报", "daily", "评估", "assess", "KPI",
    ],
    "development": [
        "代码", "code", "开发", "develop", "测试", "test", "审查", "review",
        "流水线", "pipeline",
    ],
    "content": [
        "内容", "content", "写作", "writing", "发布", "publish",
        "文章", "article",
    ],
}


class IntentClassifier:
    """Multi-level semantic intent classifier.
    多级语义意图分类器。

    Features:
        - TF-IDF weighted keyword matching across skill/tool/capability levels
        - Domain-level classification for routing context
        - Intent history tracking for preference learning
        - Compound intent detection (multi-skill queries)
    """

    def __init__(
        self,
        skill_triggers: dict[str, list[str]] | None = None,
        tool_keywords: dict[str, list[str]] | None = None,
        capability_keywords: dict[str, list[str]] | None = None,
    ):
        self._skill_triggers = skill_triggers or {}
        self._tool_keywords = tool_keywords or {}
        self._capability_keywords = capability_keywords or {}
        self._intent_history: list[dict] = []
        self._max_history = 500

        # Build IDF weights from all keyword corpora
        self._idf: dict[str, float] = {}
        self._build_idf()

    def _build_idf(self) -> None:
        """Build IDF weights from all keyword sets.
        从所有关键词集构建 IDF 权重。
        """
        all_docs: list[set[str]] = []
        for keywords in self._skill_triggers.values():
            all_docs.append({kw.lower() for kw in keywords})
        for keywords in self._tool_keywords.values():
            all_docs.append({kw.lower() for kw in keywords})
        for keywords in self._capability_keywords.values():
            all_docs.append({kw.lower() for kw in keywords})
        for keywords in DOMAIN_KEYWORDS.values():
            all_docs.append({kw.lower() for kw in keywords})

        n_docs = len(all_docs) + 1  # +1 to avoid div by zero
        term_doc_freq: Counter = Counter()
        for doc in all_docs:
            for term in doc:
                term_doc_freq[term] += 1

        for term, df in term_doc_freq.items():
            self._idf[term] = math.log(n_docs / (df + 1)) + 1.0

    def _score_keywords(self, input_lower: str, keywords: list[str]) -> tuple[float, list[str]]:
        """Score a keyword list against input using TF-IDF weighting.
        使用 TF-IDF 加权对关键词列表评分。
        """
        matched = []
        score = 0.0
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in input_lower:
                idf_weight = self._idf.get(kw_lower, 1.0)
                score += len(kw_lower) * idf_weight
                matched.append(kw)
        return score, matched

    def classify_domain(self, user_input: str) -> tuple[str, float]:
        """Classify the high-level domain of the input.
        分类输入的高级域。
        """
        input_lower = user_input.lower()
        best_domain = "general"
        best_score = 0.0
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score, _ = self._score_keywords(input_lower, keywords)
            if score > best_score:
                best_score = score
                best_domain = domain
        confidence = min(1.0, best_score / 15.0) if best_score > 0 else 0.0
        return best_domain, confidence

    def classify(self, user_input: str) -> IntentResult:
        """Classify user intent with multi-level routing.
        对用户意图进行多级路由分类。

        Args:
            user_input: Natural language input / 用户自然语言输入

        Returns:
            IntentResult with route_type, target, confidence, domain.
        """
        input_lower = user_input.lower()
        domain, domain_conf = self.classify_domain(user_input)

        # Level 1: Skill trigger matching
        skill_result = self._match_skills(input_lower)
        if skill_result and skill_result.confidence >= 0.5:
            skill_result.domain = domain
            self._record_intent(user_input, skill_result)
            return skill_result

        # Level 2: Tool keyword matching
        tool_result = self._match_tools(input_lower)
        if tool_result and tool_result.confidence >= 0.4:
            tool_result.domain = domain
            self._record_intent(user_input, tool_result)
            return tool_result

        # Level 3: Capability matching
        cap_result = self._match_capabilities(input_lower)
        if cap_result and cap_result.confidence >= 0.3:
            cap_result.domain = domain
            self._record_intent(user_input, cap_result)
            return cap_result

        # Level 4: Fall through to planning
        result = IntentResult(
            route_type="planning",
            target="planning",
            confidence=max(0.2, domain_conf * 0.5),
            domain=domain,
            metadata={"reason": "No specific match; delegating to planning agent"},
        )
        self._record_intent(user_input, result)
        return result

    def classify_compound(self, user_input: str) -> list[IntentResult]:
        """Detect compound intents (multiple actions in one query).
        检测复合意图（一个查询中的多个动作）。
        """
        input_lower = user_input.lower()
        results = []

        # Check each skill/tool for any match
        for name, triggers in self._skill_triggers.items():
            score, matched = self._score_keywords(input_lower, triggers)
            if score > 0:
                results.append(IntentResult(
                    route_type="skill",
                    target=name,
                    confidence=min(1.0, score / 15.0),
                    matched_keywords=matched,
                ))

        for name, keywords in self._tool_keywords.items():
            score, matched = self._score_keywords(input_lower, keywords)
            if score > 0:
                # Don't duplicate if skill already matched
                if not any(r.target == name for r in results):
                    results.append(IntentResult(
                        route_type="tool",
                        target=name,
                        confidence=min(1.0, score / 12.0),
                        matched_keywords=matched,
                    ))

        results.sort(key=lambda r: r.confidence, reverse=True)
        return results[:5]  # Top 5 intents

    def _match_skills(self, input_lower: str) -> IntentResult | None:
        best_name = None
        best_score = 0.0
        best_matched: list[str] = []

        for name, triggers in self._skill_triggers.items():
            score, matched = self._score_keywords(input_lower, triggers)
            if score > best_score:
                best_score = score
                best_name = name
                best_matched = matched

        if best_name and best_score > 0:
            return IntentResult(
                route_type="skill",
                target=best_name,
                confidence=min(1.0, best_score / 15.0),
                matched_keywords=best_matched,
            )
        return None

    def _match_tools(self, input_lower: str) -> IntentResult | None:
        best_name = None
        best_score = 0.0
        best_matched: list[str] = []

        for name, keywords in self._tool_keywords.items():
            score, matched = self._score_keywords(input_lower, keywords)
            if score > best_score:
                best_score = score
                best_name = name
                best_matched = matched

        if best_name and best_score > 0:
            return IntentResult(
                route_type="tool",
                target=best_name,
                confidence=min(1.0, best_score / 12.0),
                matched_keywords=best_matched,
            )
        return None

    def _match_capabilities(self, input_lower: str) -> IntentResult | None:
        best_name = None
        best_score = 0.0
        best_matched: list[str] = []

        for name, keywords in self._capability_keywords.items():
            score, matched = self._score_keywords(input_lower, keywords)
            if score > best_score:
                best_score = score
                best_name = name
                best_matched = matched

        if best_name and best_score > 0:
            return IntentResult(
                route_type="capability",
                target=best_name,
                confidence=min(1.0, best_score / 10.0),
                matched_keywords=best_matched,
            )
        return None

    # ------------------------------------------------------------------
    # Intent history
    # ------------------------------------------------------------------

    def _record_intent(self, user_input: str, result: IntentResult) -> None:
        """Record intent classification for history tracking.
        记录意图分类以供历史追踪。
        """
        entry = {
            "timestamp": time.time(),
            "input_preview": user_input[:80],
            "route_type": result.route_type,
            "target": result.target,
            "confidence": result.confidence,
            "domain": result.domain,
        }
        self._intent_history.append(entry)
        if len(self._intent_history) > self._max_history:
            self._intent_history = self._intent_history[-self._max_history:]

    def get_intent_history(self, limit: int = 20) -> list[dict]:
        """Get recent intent classification history.
        获取近期意图分类历史。
        """
        return list(reversed(self._intent_history[-limit:]))

    def get_routing_stats(self) -> dict:
        """Get routing statistics from intent history.
        从意图历史获取路由统计。
        """
        type_counts: Counter = Counter()
        target_counts: Counter = Counter()
        domain_counts: Counter = Counter()
        for entry in self._intent_history:
            type_counts[entry["route_type"]] += 1
            target_counts[entry["target"]] += 1
            domain_counts[entry["domain"]] += 1

        return {
            "total_classifications": len(self._intent_history),
            "by_route_type": dict(type_counts),
            "by_target": dict(target_counts.most_common(10)),
            "by_domain": dict(domain_counts),
        }
