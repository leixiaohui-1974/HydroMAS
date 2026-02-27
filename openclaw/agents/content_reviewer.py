"""ContentReviewerAgent — reviews content quality before publishing.
内容审查Agent — 在发布前审查内容质量。

Review dimensions:
1. Structure: outline, headings, flow
2. Style: tone consistency, readability
3. Technical: accuracy, terminology, references
4. Compliance: sensitive content, formatting standards
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ReviewComment:
    """A single review comment. / 单条审查意见。"""

    category: str  # structure, style, technical, compliance
    severity: str = "info"  # info, warning, error
    location: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "location": self.location,
            "message": self.message,
        }


@dataclass
class ContentReviewResult:
    """Result of a content review. / 内容审查结果。"""

    passed: bool = True
    score: float = 100.0
    comments: list[ReviewComment] = field(default_factory=list)
    summary: str = ""

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "comments": [c.to_dict() for c in self.comments],
            "summary": self.summary,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


# Style rules
_MIN_SECTION_LENGTH = 100  # characters
_MAX_SECTION_LENGTH = 3000
_SENSITIVE_PATTERNS = [
    r"密钥|secret|password|token|api.?key",
    r"内部.*机密|confidential",
]


class ContentReviewerAgent:
    """Content Reviewer Agent — multi-dimensional content review.
    内容审查Agent — 多维度内容审查。
    """

    def review_article(
        self,
        content: str,
        config: dict | None = None,
    ) -> ContentReviewResult:
        """Review an article's content quality.
        审查文章内容质量。
        """
        result = ContentReviewResult()
        config = config or {}

        # Run all review dimensions
        self._check_structure(content, result)
        self._check_style(content, result)
        self._check_technical(content, result, config)
        self._check_compliance(content, result)

        # Calculate score
        penalty = result.error_count * 15 + result.warning_count * 5
        result.score = max(0, 100 - penalty)
        result.passed = result.error_count == 0 and result.score >= 60

        # Generate summary
        result.summary = self._generate_summary(result)
        return result

    def review_image_config(self, config: dict) -> ContentReviewResult:
        """Review an image pipeline configuration.
        审查图片流水线配置。
        """
        result = ContentReviewResult()
        images = config.get("images", [])

        if not images:
            result.comments.append(ReviewComment(
                category="structure",
                severity="error",
                message="No images defined in configuration",
            ))

        for i, img in enumerate(images):
            loc = f"images[{i}]"
            if "prompt" not in img:
                result.comments.append(ReviewComment(
                    category="structure",
                    severity="error",
                    location=loc,
                    message="Missing 'prompt' field",
                ))
            elif len(img["prompt"]) < 20:
                result.comments.append(ReviewComment(
                    category="style",
                    severity="warning",
                    location=loc,
                    message="Prompt too short, may produce low-quality image",
                ))
            if "filename" not in img:
                result.comments.append(ReviewComment(
                    category="structure",
                    severity="error",
                    location=loc,
                    message="Missing 'filename' field",
                ))

        penalty = result.error_count * 15 + result.warning_count * 5
        result.score = max(0, 100 - penalty)
        result.passed = result.error_count == 0
        result.summary = self._generate_summary(result)
        return result

    def review_publish_config(self, config: dict) -> ContentReviewResult:
        """Review a publish configuration."""
        result = ContentReviewResult()

        if not config.get("doc_token"):
            result.comments.append(ReviewComment(
                category="structure",
                severity="error",
                message="Missing doc_token",
            ))

        # Check for exposed secrets
        for key in ["app_secret", "api_key", "wechat_app_secret"]:
            for section in [config.get("feishu", {}), config.get("wechat", {}), config]:
                val = section.get(key, "")
                if val and not val.startswith("YOUR_") and len(val) > 10:
                    result.comments.append(ReviewComment(
                        category="compliance",
                        severity="warning",
                        message=f"Possible exposed secret in '{key}' — ensure desensitized",
                    ))

        penalty = result.error_count * 15 + result.warning_count * 5
        result.score = max(0, 100 - penalty)
        result.passed = result.error_count == 0
        result.summary = self._generate_summary(result)
        return result

    def _check_structure(self, content: str, result: ContentReviewResult) -> None:
        """Check article structure. / 检查文章结构。"""
        lines = content.strip().split("\n")
        headings = [ln for ln in lines if ln.startswith("#")]

        if len(headings) < 2:
            result.comments.append(ReviewComment(
                category="structure",
                severity="warning",
                message="Article has fewer than 2 headings — consider adding structure",
            ))

        if len(content) < 200:
            result.comments.append(ReviewComment(
                category="structure",
                severity="warning",
                message=f"Article very short ({len(content)} chars)",
            ))

        # Check sections between headings
        sections = re.split(r'\n#{1,3}\s', content)
        for i, section in enumerate(sections):
            if len(section.strip()) > _MAX_SECTION_LENGTH:
                result.comments.append(ReviewComment(
                    category="structure",
                    severity="info",
                    location=f"section_{i}",
                    message="Section is very long — consider splitting",
                ))

    def _check_style(self, content: str, result: ContentReviewResult) -> None:
        """Check writing style. / 检查写作风格。"""
        # Check for excessive exclamation marks
        if content.count("!") + content.count("！") > 10:
            result.comments.append(ReviewComment(
                category="style",
                severity="info",
                message="Many exclamation marks — consider toning down",
            ))

        # Check for TODO markers
        todos = re.findall(r"TODO|FIXME|HACK|XXX", content, re.IGNORECASE)
        if todos:
            result.comments.append(ReviewComment(
                category="style",
                severity="warning",
                message=f"Found {len(todos)} TODO/FIXME markers — resolve before publishing",
            ))

    def _check_technical(
        self, content: str, result: ContentReviewResult, config: dict,
    ) -> None:
        """Check technical accuracy. / 检查技术准确性。"""
        # Check for broken markdown links
        broken_links = re.findall(r'\[([^\]]*)\]\(\s*\)', content)
        for link_text in broken_links:
            result.comments.append(ReviewComment(
                category="technical",
                severity="error",
                message=f"Broken link: [{link_text}]()",
            ))

        # Check for unresolved figure placeholders
        fig_placeholders = re.findall(r'\[FIG-TODO[^\]]*\]', content)
        if fig_placeholders:
            result.comments.append(ReviewComment(
                category="technical",
                severity="warning",
                message=f"Found {len(fig_placeholders)} unresolved [FIG-TODO] placeholders",
            ))

    def _check_compliance(self, content: str, result: ContentReviewResult) -> None:
        """Check compliance / sensitive content. / 检查合规性/敏感内容。"""
        for pattern in _SENSITIVE_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                result.comments.append(ReviewComment(
                    category="compliance",
                    severity="warning",
                    message=f"Possible sensitive content: {matches[0]}",
                ))

    def _generate_summary(self, result: ContentReviewResult) -> str:
        """Generate review summary."""
        status = "PASSED" if result.passed else "NEEDS REVISION"
        return (
            f"Review {status} (score: {result.score:.0f}/100). "
            f"{result.error_count} errors, {result.warning_count} warnings."
        )
