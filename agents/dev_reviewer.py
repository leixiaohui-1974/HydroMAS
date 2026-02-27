"""Development Reviewer Agent — code quality and design review.
开发评审 Agent — 代码质量与设计审查。

Performs multi-dimensional review of code changes following
established project standards (architecture, safety, style).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReviewComment:
    """A single review comment. / 单条评审意见。"""

    file: str
    line: int | None = None
    severity: str = "info"  # info, suggestion, warning, error
    category: str = "general"
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
        }


@dataclass
class ReviewResult:
    """Aggregated review result. / 汇总评审结果。"""

    approved: bool = True
    comments: list[ReviewComment] = field(default_factory=list)
    summary: str = ""
    scores: dict = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "comments": [c.to_dict() for c in self.comments],
            "summary": self.summary,
            "scores": self.scores,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


# ---------------------------------------------------------------------------
# Review rule definitions
# ---------------------------------------------------------------------------

ARCHITECTURE_RULES = [
    {
        "id": "ARCH-001",
        "name": "layer_dependency",
        "description": "L0 core must not import from L2+ layers",
        "pattern": r"from\s+(mcp_servers|skills|agents)\b",
        "applies_to": "core/",
        "severity": "error",
    },
    {
        "id": "ARCH-002",
        "name": "skill_tool_coupling",
        "description": "Skills should call tools via call_tool, not direct import",
        "pattern": r"from\s+mcp_servers\.\w+\s+import",
        "applies_to": "skills/",
        "severity": "warning",
    },
    {
        "id": "ARCH-003",
        "name": "agent_skill_bypass",
        "description": "Agents should not directly import core modules",
        "pattern": r"from\s+core\.\w+\s+import",
        "applies_to": "agents/",
        "severity": "warning",
    },
]

SAFETY_RULES = [
    {
        "id": "SAFE-001",
        "name": "hardcoded_credentials",
        "description": "No hardcoded passwords or API keys",
        "pattern": (
            r"(?:password|secret|api_key|token)\s*="
            r"\s*[\"'][^\"']+[\"']"
        ),
        "severity": "error",
    },
    {
        "id": "SAFE-002",
        "name": "sql_injection",
        "description": "No string-formatted SQL queries",
        "pattern": r"(?:execute|cursor)\s*\(\s*f[\"']",
        "severity": "error",
    },
    {
        "id": "SAFE-003",
        "name": "eval_usage",
        "description": "Avoid eval() and exec()",
        "pattern": r"\beval\s*\(|\bexec\s*\(",
        "severity": "warning",
    },
]

STYLE_RULES = [
    {
        "id": "STYLE-001",
        "name": "missing_docstring",
        "description": "Public classes and functions should have docstrings",
        "check": "docstring",
        "severity": "suggestion",
    },
    {
        "id": "STYLE-002",
        "name": "magic_numbers",
        "description": "Avoid magic numbers in business logic",
        "pattern": r"(?<!=\s)(?<!\w)\d{3,}(?:\.\d+)?(?!\w)",
        "severity": "info",
    },
]

DOMAIN_RULES = [
    {
        "id": "DOM-001",
        "name": "physical_bounds",
        "description": "Water level, flow, pressure must be non-negative",
        "pattern": r"(?:level|flow|pressure)\s*[<>]=?\s*-\d",
        "severity": "warning",
    },
    {
        "id": "DOM-002",
        "name": "unit_consistency",
        "description": "Check m³/d vs m³/h consistency in comments",
        "pattern": r"m[³3]/[dh]",
        "check": "unit_comment",
        "severity": "info",
    },
]


# ---------------------------------------------------------------------------
# DevReviewerAgent
# ---------------------------------------------------------------------------

class DevReviewerAgent:
    """Development Reviewer — multi-dimensional code review.
    开发评审 Agent — 多维度代码审查。

    Review dimensions:
    1. Architecture compliance (层级依赖)
    2. Safety checks (安全检查)
    3. Code style (代码风格)
    4. Domain correctness (领域正确性)
    5. Test coverage (测试覆盖)
    """

    def __init__(self) -> None:
        self._rules = {
            "architecture": ARCHITECTURE_RULES,
            "safety": SAFETY_RULES,
            "style": STYLE_RULES,
            "domain": DOMAIN_RULES,
        }

    def review_code(
        self,
        files: dict[str, str],
        context: dict | None = None,
    ) -> ReviewResult:
        """Review a set of code files.
        审查一组代码文件。

        Args:
            files: mapping of file_path → file_content
            context: optional context (requirement, design doc, etc.)

        Returns:
            ReviewResult with comments and approval decision.
        """
        result = ReviewResult()
        scores: dict[str, float] = {}

        for filepath, content in files.items():
            # Architecture review
            arch_comments = self._check_architecture(filepath, content)
            result.comments.extend(arch_comments)

            # Safety review
            safety_comments = self._check_safety(filepath, content)
            result.comments.extend(safety_comments)

            # Style review
            style_comments = self._check_style(filepath, content)
            result.comments.extend(style_comments)

            # Domain review
            domain_comments = self._check_domain(filepath, content)
            result.comments.extend(domain_comments)

        # Test coverage check
        if context and "test_files" in context:
            test_comments = self._check_test_coverage(
                files, context["test_files"],
            )
            result.comments.extend(test_comments)

        # Calculate scores
        total = max(len(files), 1)
        for category in ["architecture", "safety", "style", "domain"]:
            cat_errors = sum(
                1 for c in result.comments
                if c.category == category and c.severity in ("error", "warning")
            )
            scores[category] = max(0.0, 1.0 - cat_errors / total)
        scores["overall"] = sum(scores.values()) / len(scores) if scores else 1.0
        result.scores = scores

        # Approval decision
        result.approved = result.error_count == 0
        result.summary = self._generate_summary(result)

        logger.info(
            "DevReviewer: reviewed %d files, %d errors, %d warnings, approved=%s",
            len(files), result.error_count, result.warning_count,
            result.approved,
        )
        return result

    def review_design(self, design_doc: dict) -> ReviewResult:
        """Review a design document for completeness and feasibility.
        审查设计文档的完整性和可行性。
        """
        result = ReviewResult()

        req = design_doc.get("requirement", {})
        plan = design_doc.get("implementation_plan", {})
        tasks = plan.get("tasks", [])

        # Check requirement completeness
        if not req.get("acceptance_criteria"):
            result.comments.append(ReviewComment(
                file="design_doc",
                severity="suggestion",
                category="completeness",
                message="Missing acceptance criteria in requirement",
            ))

        # Check plan has test tasks
        has_test_task = any("test" in t.get("id", "").lower() for t in tasks)
        if not has_test_task:
            result.comments.append(ReviewComment(
                file="design_doc",
                severity="warning",
                category="completeness",
                message="Implementation plan has no test tasks",
            ))

        # Check plan has review tasks
        has_review_task = any(
            "review" in t.get("id", "").lower() for t in tasks
        )
        if not has_review_task:
            result.comments.append(ReviewComment(
                file="design_doc",
                severity="warning",
                category="completeness",
                message="Implementation plan has no review tasks",
            ))

        # Check risk assessment
        if not design_doc.get("risk_notes"):
            result.comments.append(ReviewComment(
                file="design_doc",
                severity="suggestion",
                category="completeness",
                message="Missing risk assessment",
            ))

        result.approved = result.error_count == 0
        result.summary = self._generate_summary(result)
        return result

    # ----- Rule-based checks -----

    def _check_architecture(
        self, filepath: str, content: str,
    ) -> list[ReviewComment]:
        comments = []
        for rule in self._rules["architecture"]:
            if rule["applies_to"] not in filepath:
                continue
            pattern = rule.get("pattern")
            if not pattern:
                continue
            for i, line in enumerate(content.splitlines(), start=1):
                if re.search(pattern, line):
                    comments.append(ReviewComment(
                        file=filepath,
                        line=i,
                        severity=rule["severity"],
                        category="architecture",
                        message=f"[{rule['id']}] {rule['description']}",
                    ))
        return comments

    def _check_safety(
        self, filepath: str, content: str,
    ) -> list[ReviewComment]:
        comments = []
        for rule in self._rules["safety"]:
            pattern = rule.get("pattern")
            if not pattern:
                continue
            for i, line in enumerate(content.splitlines(), start=1):
                if re.search(pattern, line, re.IGNORECASE):
                    comments.append(ReviewComment(
                        file=filepath,
                        line=i,
                        severity=rule["severity"],
                        category="safety",
                        message=f"[{rule['id']}] {rule['description']}",
                    ))
        return comments

    def _check_style(
        self, filepath: str, content: str,
    ) -> list[ReviewComment]:
        comments = []
        for rule in self._rules["style"]:
            if rule.get("check") == "docstring":
                comments.extend(self._check_docstrings(filepath, content))
            elif rule.get("pattern"):
                for i, line in enumerate(content.splitlines(), start=1):
                    if re.search(rule["pattern"], line):
                        comments.append(ReviewComment(
                            file=filepath,
                            line=i,
                            severity=rule["severity"],
                            category="style",
                            message=(
                                f"[{rule['id']}] {rule['description']}"
                            ),
                        ))
        return comments

    def _check_domain(
        self, filepath: str, content: str,
    ) -> list[ReviewComment]:
        comments = []
        for rule in self._rules["domain"]:
            pattern = rule.get("pattern")
            if not pattern:
                continue
            for i, line in enumerate(content.splitlines(), start=1):
                if re.search(pattern, line):
                    comments.append(ReviewComment(
                        file=filepath,
                        line=i,
                        severity=rule["severity"],
                        category="domain",
                        message=f"[{rule['id']}] {rule['description']}",
                    ))
        return comments

    @staticmethod
    def _check_docstrings(
        filepath: str, content: str,
    ) -> list[ReviewComment]:
        """Check that public functions and classes have docstrings."""
        comments = []
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("def ", "class ")) and not stripped.startswith("def _"):
                # Check next non-empty line for docstring
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if not (
                        next_line.startswith('"""')
                        or next_line.startswith("'''")
                    ):
                        comments.append(ReviewComment(
                            file=filepath,
                            line=i + 1,
                            severity="suggestion",
                            category="style",
                            message=(
                                "[STYLE-001] Missing docstring for "
                                f"'{stripped[:50]}'"
                            ),
                        ))
        return comments

    @staticmethod
    def _check_test_coverage(
        source_files: dict[str, str],
        test_files: dict[str, str],
    ) -> list[ReviewComment]:
        """Check that source files have corresponding test files."""
        comments = []
        test_names = set()
        for tf_content in test_files.values():
            for match in re.finditer(r"def (test_\w+)", tf_content):
                test_names.add(match.group(1))

        for filepath in source_files:
            basename = filepath.rsplit("/", 1)[-1].replace(".py", "")
            expected_test = f"test_{basename}"
            has_test = any(expected_test in tn for tn in test_names)
            if not has_test:
                comments.append(ReviewComment(
                    file=filepath,
                    severity="warning",
                    category="test_coverage",
                    message=f"No test functions found matching '{expected_test}_*'",
                ))
        return comments

    @staticmethod
    def _generate_summary(result: ReviewResult) -> str:
        """Generate human-readable review summary."""
        status = "APPROVED" if result.approved else "CHANGES REQUESTED"
        parts = [f"Review: {status}"]
        if result.error_count:
            parts.append(f"{result.error_count} error(s)")
        if result.warning_count:
            parts.append(f"{result.warning_count} warning(s)")
        info_count = sum(
            1 for c in result.comments
            if c.severity in ("info", "suggestion")
        )
        if info_count:
            parts.append(f"{info_count} suggestion(s)")
        if result.scores:
            overall = result.scores.get("overall", 0)
            parts.append(f"overall score: {overall:.2f}")
        return " | ".join(parts)
