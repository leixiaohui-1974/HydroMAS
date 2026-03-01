"""Tests for HydroClaw evolution (interaction logging + analysis).
HydroClaw 自进化系统测试。
"""

import json
import time
from pathlib import Path

import pytest

from hydroclaw.evolution.logger import InteractionLogger, InteractionRecord
from hydroclaw.evolution.analyzer import EvolutionAnalyzer, EvolutionReport


class TestInteractionRecord:
    """Test InteractionRecord dataclass."""

    def test_to_dict(self):
        rec = InteractionRecord(
            user_id="u1",
            message="水平衡",
            skill_used="water_balance",
            success=True,
            response_time_ms=150.5,
        )
        d = rec.to_dict()
        assert d["user_id"] == "u1"
        assert d["message"] == "水平衡"
        assert d["skill_used"] == "water_balance"
        assert d["success"] is True
        assert d["response_time_ms"] == 150.5


class TestInteractionLogger:
    """Test InteractionLogger."""

    @pytest.fixture
    def logger(self, tmp_path):
        return InteractionLogger(log_dir=tmp_path)

    def test_log_and_retrieve(self, logger):
        logger.log_chat(
            message="水平衡查询",
            user_id="user1",
            skill_used="water_balance",
            success=True,
            response_time_ms=100,
        )
        records = logger.get_records()
        assert len(records) == 1
        assert records[0]["message"] == "水平衡查询"

    def test_log_multiple(self, logger):
        for i in range(10):
            logger.log_chat(
                message=f"Query {i}",
                user_id=f"user{i % 3}",
                success=True,
            )
        records = logger.get_records()
        assert len(records) == 10

    def test_filter_by_user(self, logger):
        logger.log_chat(message="Q1", user_id="alice")
        logger.log_chat(message="Q2", user_id="bob")
        logger.log_chat(message="Q3", user_id="alice")

        alice_records = logger.get_records(user_id="alice")
        assert len(alice_records) == 2

    def test_get_stats(self, logger):
        logger.log_chat(message="Q1", user_id="u1", skill_used="forecast", success=True, response_time_ms=100)
        logger.log_chat(message="Q2", user_id="u2", skill_used="forecast", success=True, response_time_ms=200)
        logger.log_chat(message="Q3", user_id="u1", skill_used="dispatch", success=False, error="timeout")

        stats = logger.get_stats()
        assert stats["total"] == 3
        assert stats["unique_users"] == 2
        assert stats["success_rate"] == pytest.approx(66.7, abs=0.1)
        assert stats["error_count"] == 1

    def test_available_dates(self, logger):
        logger.log_chat(message="test")
        dates = logger.get_available_dates()
        assert len(dates) >= 1

    def test_empty_stats(self, logger):
        stats = logger.get_stats(date="2020-01-01")
        assert stats["total"] == 0

    def test_log_record_directly(self, logger):
        rec = InteractionRecord(
            user_id="test",
            message="直接记录",
            intent_type="skill",
            intent_target="forecast",
        )
        logger.log(rec)
        records = logger.get_records()
        assert len(records) == 1
        assert records[0]["intent_type"] == "skill"


class TestEvolutionAnalyzer:
    """Test EvolutionAnalyzer."""

    @pytest.fixture
    def setup_logs(self, tmp_path):
        """Create test interaction logs."""
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        log_file = tmp_path / f"interactions_{date}.jsonl"

        records = [
            # Successful requests
            {"timestamp": time.time(), "user_id": "u1", "message": "水平衡",
             "skill_used": "water_balance", "success": True, "response_time_ms": 100,
             "intent_type": "skill", "intent_target": "water_balance"},
            {"timestamp": time.time(), "user_id": "u2", "message": "ODD检查",
             "skill_used": "odd_assessment", "success": True, "response_time_ms": 200,
             "intent_type": "skill", "intent_target": "odd_assessment"},
            # Failed request
            {"timestamp": time.time(), "user_id": "u1", "message": "泄漏检测",
             "skill_used": "leak_diagnosis", "success": False, "response_time_ms": 5500,
             "error": "GNN model not available", "intent_type": "skill", "intent_target": "leak_diagnosis"},
            {"timestamp": time.time(), "user_id": "u2", "message": "泄漏检测2",
             "skill_used": "leak_diagnosis", "success": False, "response_time_ms": 5200,
             "error": "GNN model not available", "intent_type": "skill", "intent_target": "leak_diagnosis"},
            {"timestamp": time.time(), "user_id": "u3", "message": "泄漏检测3",
             "skill_used": "leak_diagnosis", "success": False, "response_time_ms": 5300,
             "error": "GNN model timeout", "intent_type": "skill", "intent_target": "leak_diagnosis"},
            # Unrouted request
            {"timestamp": time.time(), "user_id": "u1", "message": "天气怎么样",
             "skill_used": "", "success": True, "response_time_ms": 50,
             "intent_type": "unknown", "intent_target": ""},
        ]

        with open(log_file, "w") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        return tmp_path

    def test_analyze_empty(self, tmp_path):
        analyzer = EvolutionAnalyzer(interaction_dir=tmp_path)
        report = analyzer.analyze(days_back=7)
        assert report.total_interactions == 0
        assert len(report.improvements) == 0

    def test_analyze_with_data(self, setup_logs):
        analyzer = EvolutionAnalyzer(interaction_dir=setup_logs)
        report = analyzer.analyze(days_back=1)
        assert report.total_interactions == 6
        assert report.unique_users == 3

    def test_detect_failures(self, setup_logs):
        analyzer = EvolutionAnalyzer(interaction_dir=setup_logs)
        report = analyzer.analyze(days_back=1)
        # Should detect leak_diagnosis high failure rate
        failure_items = [i for i in report.improvements if i.category == "bug_fix"]
        assert len(failure_items) > 0
        assert any("leak_diagnosis" in str(i.affected_skills) for i in failure_items)

    def test_detect_slow_responses(self, setup_logs):
        analyzer = EvolutionAnalyzer(interaction_dir=setup_logs)
        report = analyzer.analyze(days_back=1)
        slow_items = [i for i in report.improvements if i.category == "performance"]
        assert len(slow_items) > 0

    def test_report_to_dict(self, setup_logs):
        analyzer = EvolutionAnalyzer(interaction_dir=setup_logs)
        report = analyzer.analyze(days_back=1)
        d = report.to_dict()
        assert "total_interactions" in d
        assert "improvements" in d
        assert "statistics" in d

    def test_report_to_markdown(self, setup_logs):
        analyzer = EvolutionAnalyzer(interaction_dir=setup_logs)
        report = analyzer.analyze(days_back=1)
        md = report.to_markdown()
        assert "# 自进化分析报告" in md
        assert "改进建议" in md


class TestEvolutionReport:
    """Test EvolutionReport dataclass."""

    def test_empty_report(self):
        report = EvolutionReport(
            analysis_date="2026-03-01",
            period_start="2026-02-22",
            period_end="2026-03-01",
        )
        assert report.total_interactions == 0
        md = report.to_markdown()
        assert "2026-03-01" in md
