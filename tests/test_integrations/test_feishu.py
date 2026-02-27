"""Tests for Feishu integration modules."""

from __future__ import annotations

from integrations.feishu_alert import (
    AlertEvent,
    FeishuAlertSender,
    build_alert_card,
)
from integrations.feishu_bot import (
    FeishuBotHandler,
    FeishuCardResponse,
    FeishuMessage,
)
from integrations.feishu_sync import (
    HYDROMAS_TABLES,
    BitableRecord,
    FeishuBitableSync,
)

# ===== FeishuBot Tests =====

class TestFeishuMessage:
    """Test FeishuMessage data class."""

    def test_to_dict(self):
        msg = FeishuMessage(
            msg_id="m1", chat_id="c1",
            user_id="u1", text="hello",
        )
        d = msg.to_dict()
        assert d["msg_id"] == "m1"
        assert d["text"] == "hello"

    def test_default_values(self):
        msg = FeishuMessage()
        assert msg.msg_type == "text"
        assert msg.timestamp != ""


class TestFeishuCardResponse:
    """Test card response building."""

    def test_basic_card(self):
        card = FeishuCardResponse(
            title="Test",
            content="Hello world",
            status="success",
        )
        j = card.to_card_json()
        assert j["header"]["template"] == "green"
        assert j["header"]["title"]["content"] == "Test"

    def test_card_with_actions(self):
        card = FeishuCardResponse(
            title="Alert",
            content="Something happened",
            status="warning",
            actions=[
                {"label": "Fix", "value": {"cmd": "fix"}},
                {"label": "Ignore", "value": {"cmd": "ignore"}},
            ],
        )
        j = card.to_card_json()
        assert j["header"]["template"] == "orange"
        # Should have action element
        has_action = any(
            e.get("tag") == "action" for e in j["elements"]
        )
        assert has_action


class TestFeishuBotHandler:
    """Test bot message handling."""

    def setup_method(self):
        self.handler = FeishuBotHandler()

    def test_command_map_populated(self):
        assert len(self.handler.COMMAND_MAP) > 0
        assert "/水平衡" in self.handler.COMMAND_MAP
        assert "/日报" in self.handler.COMMAND_MAP

    def test_webhook_challenge(self):
        result = self.handler.verify_webhook({"challenge": "abc123"})
        assert result == {"challenge": "abc123"}

    def test_webhook_no_challenge(self):
        result = self.handler.verify_webhook({"event": {}})
        assert result is None


# ===== FeishuAlert Tests =====

class TestAlertEvent:
    """Test AlertEvent data class."""

    def test_to_dict(self):
        event = AlertEvent(
            alert_id="A001",
            severity="critical",
            dimension="water_level",
            message="Level too high",
            value=0.98,
            threshold=0.95,
        )
        d = event.to_dict()
        assert d["alert_id"] == "A001"
        assert d["severity"] == "critical"


class TestBuildAlertCard:
    """Test alert card building."""

    def test_info_card(self):
        event = AlertEvent(severity="info", dimension="test")
        card = build_alert_card(event)
        assert card["card"]["header"]["template"] == "blue"

    def test_warning_card(self):
        event = AlertEvent(severity="warning", dimension="test")
        card = build_alert_card(event)
        assert card["card"]["header"]["template"] == "orange"

    def test_critical_card(self):
        event = AlertEvent(severity="critical", dimension="test")
        card = build_alert_card(event)
        assert card["card"]["header"]["template"] == "red"

    def test_card_with_actions(self):
        event = AlertEvent(
            severity="warning",
            dimension="water_level",
            actions=["一键诊断", "忽略"],
        )
        card = build_alert_card(event)
        elements = card["card"]["elements"]
        action_elem = [e for e in elements if e.get("tag") == "action"]
        assert len(action_elem) == 1
        assert len(action_elem[0]["actions"]) == 2


class TestFeishuAlertSender:
    """Test alert sender."""

    def setup_method(self):
        self.sender = FeishuAlertSender()

    def test_send_alert(self):
        event = AlertEvent(
            alert_id="T001",
            severity="warning",
            dimension="pressure",
        )
        card = self.sender.send_alert(event)
        assert card["msg_type"] == "interactive"
        assert len(self.sender.get_history()) == 1

    def test_send_from_safety_result(self):
        safety_result = {
            "violations": [
                {
                    "dimension": "water_level",
                    "zone": "red",
                    "value": 1.2,
                    "threshold": 0.95,
                    "message": "Level critical",
                },
                {
                    "dimension": "pressure",
                    "zone": "yellow",
                    "value": 4.5,
                    "threshold": 4.0,
                    "message": "Pressure high",
                },
            ],
        }
        cards = self.sender.send_from_safety_result(safety_result)
        assert len(cards) == 2
        assert len(self.sender.get_history()) == 2

    def test_send_from_leak_result_detected(self):
        leak_result = {
            "leak_detected": True,
            "location": "pipe_segment_7",
            "residual": 150,
            "threshold": 50,
        }
        card = self.sender.send_from_leak_result(leak_result)
        assert card is not None
        assert card["card"]["header"]["template"] == "red"

    def test_send_from_leak_result_no_leak(self):
        leak_result = {"leak_detected": False}
        card = self.sender.send_from_leak_result(leak_result)
        assert card is None


# ===== FeishuSync Tests =====

class TestBitableRecord:
    """Test BitableRecord data class."""

    def test_to_dict(self):
        r = BitableRecord(
            table_id="t1",
            record_id="r1",
            fields={"name": "test"},
        )
        d = r.to_dict()
        assert d["table_id"] == "t1"
        assert d["fields"]["name"] == "test"


class TestFeishuBitableSync:
    """Test Bitable sync operations."""

    def setup_method(self):
        self.sync = FeishuBitableSync()

    def test_sync_pipeline_run(self):
        pipeline = {
            "id": "DEV-0001",
            "requirement": "Test task",
            "status": "completed",
            "stages": [
                {"name": "planning", "status": "completed"},
                {"name": "review", "status": "completed"},
                {"name": "testing", "status": "completed"},
            ],
            "iteration": 1,
            "created_at": "2026-02-27",
        }
        result = self.sync.sync_pipeline_run(pipeline)
        assert result.success
        assert result.records_synced == 1

    def test_sync_water_kpi(self):
        kpi = {
            "date": "2026-02-27",
            "daily_intake": 10400,
            "daily_reuse": 3744,
            "reuse_rate": 0.36,
            "daily_evaporation": 4200,
        }
        result = self.sync.sync_water_kpi(kpi)
        assert result.success

    def test_sync_alert(self):
        alert = {
            "alert_id": "A001",
            "severity": "warning",
            "dimension": "water_level",
            "value": 0.92,
            "threshold": 0.90,
        }
        result = self.sync.sync_alert(alert)
        assert result.success

    def test_sync_dev_task(self):
        task = {
            "id": "TASK-001",
            "description": "Implement feature X",
            "assignee": "Alice",
            "status": "in_progress",
            "priority": "high",
        }
        result = self.sync.sync_dev_task(task)
        assert result.success

    def test_flush_batch(self):
        self.sync.sync_water_kpi({"date": "2026-02-27"})
        self.sync.sync_water_kpi({"date": "2026-02-28"})
        self.sync.sync_alert({"alert_id": "A1"})

        result = self.sync.flush()
        assert result.records_synced == 3
        # After flush, pending should be empty
        result2 = self.sync.flush()
        assert result2.records_synced == 0

    def test_table_schemas(self):
        schemas = self.sync.get_table_schemas()
        assert "pipeline_runs" in schemas
        assert "water_kpi" in schemas
        assert "alerts" in schemas
        assert "dev_tasks" in schemas

    def test_hydromas_tables_complete(self):
        for table_name, table_def in HYDROMAS_TABLES.items():
            assert "name" in table_def
            assert "fields" in table_def
            assert len(table_def["fields"]) > 0
