"""Tests for ContentReviewerAgent."""

from __future__ import annotations

from openclaw.agents.content_reviewer import (
    ContentReviewerAgent,
    ContentReviewResult,
    ReviewComment,
)

_GOOD_ARTICLE = """# AI CLI Tools: The New Frontier

## Introduction

The emergence of CLI tools from major AI companies marks a significant shift.

## Background

Companies like Anthropic, Google, and OpenAI have all launched CLI tools.

## Analysis

Each tool has distinct characteristics and target audiences.

## Conclusion

CLI tools represent the evolution from conversation to collaboration.
"""

_BAD_ARTICLE = "Short."

_ARTICLE_WITH_ISSUES = """# Test Article

This has a [broken link]() and a [FIG-TODO: diagram] placeholder.

Also mentions a password=secret123 and has TODO: fix this.
"""


class TestArticleReview:
    def setup_method(self):
        self.reviewer = ContentReviewerAgent()

    def test_good_article_passes(self):
        result = self.reviewer.review_article(_GOOD_ARTICLE)
        assert result.passed
        assert result.score >= 80

    def test_short_article_warning(self):
        result = self.reviewer.review_article(_BAD_ARTICLE)
        assert result.warning_count > 0

    def test_broken_link_detected(self):
        result = self.reviewer.review_article(_ARTICLE_WITH_ISSUES)
        categories = [c.category for c in result.comments]
        assert "technical" in categories

    def test_todo_detected(self):
        result = self.reviewer.review_article(_ARTICLE_WITH_ISSUES)
        messages = " ".join(c.message for c in result.comments)
        assert "TODO" in messages or "FIXME" in messages

    def test_sensitive_content_detected(self):
        result = self.reviewer.review_article(_ARTICLE_WITH_ISSUES)
        categories = [c.category for c in result.comments]
        assert "compliance" in categories

    def test_fig_placeholder_detected(self):
        result = self.reviewer.review_article(_ARTICLE_WITH_ISSUES)
        messages = " ".join(c.message for c in result.comments)
        assert "FIG-TODO" in messages

    def test_score_decreases_with_errors(self):
        good = self.reviewer.review_article(_GOOD_ARTICLE)
        bad = self.reviewer.review_article(_ARTICLE_WITH_ISSUES)
        assert good.score > bad.score

    def test_summary_generated(self):
        result = self.reviewer.review_article(_GOOD_ARTICLE)
        assert "PASSED" in result.summary or "NEEDS" in result.summary

    def test_to_dict(self):
        result = self.reviewer.review_article(_GOOD_ARTICLE)
        d = result.to_dict()
        assert "passed" in d
        assert "score" in d
        assert "comments" in d


class TestImageConfigReview:
    def setup_method(self):
        self.reviewer = ContentReviewerAgent()

    def test_valid_config(self):
        config = {
            "images": [
                {"filename": "test.png", "prompt": "A detailed infographic showing data flow"},
            ],
        }
        result = self.reviewer.review_image_config(config)
        assert result.passed

    def test_empty_images(self):
        config = {"images": []}
        result = self.reviewer.review_image_config(config)
        assert not result.passed

    def test_missing_prompt(self):
        config = {"images": [{"filename": "test.png"}]}
        result = self.reviewer.review_image_config(config)
        assert not result.passed

    def test_short_prompt_warning(self):
        config = {
            "images": [{"filename": "test.png", "prompt": "A cat"}],
        }
        result = self.reviewer.review_image_config(config)
        assert result.warning_count > 0


class TestPublishConfigReview:
    def setup_method(self):
        self.reviewer = ContentReviewerAgent()

    def test_valid_config(self):
        config = {
            "doc_token": "abc123",
            "feishu": {"app_id": "cli_xxx", "app_secret": "YOUR_SECRET"},
        }
        result = self.reviewer.review_publish_config(config)
        assert result.passed

    def test_missing_doc_token(self):
        config = {"feishu": {"app_id": "cli_xxx"}}
        result = self.reviewer.review_publish_config(config)
        assert not result.passed

    def test_exposed_secret_warning(self):
        config = {
            "doc_token": "abc123",
            "feishu": {"app_id": "cli_xxx", "app_secret": "a_real_secret_value_here"},
        }
        result = self.reviewer.review_publish_config(config)
        assert result.warning_count > 0


class TestReviewDataClasses:
    def test_review_comment(self):
        c = ReviewComment(category="style", severity="warning", message="Too long")
        d = c.to_dict()
        assert d["category"] == "style"
        assert d["severity"] == "warning"

    def test_review_result_counts(self):
        r = ContentReviewResult()
        r.comments.append(ReviewComment(category="a", severity="error", message="bad"))
        r.comments.append(ReviewComment(category="b", severity="warning", message="ok"))
        r.comments.append(ReviewComment(category="c", severity="info", message="fyi"))
        assert r.error_count == 1
        assert r.warning_count == 1
