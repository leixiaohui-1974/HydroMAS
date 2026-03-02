"""End-to-end tests for Feishu bot integration.
飞书机器人端到端测试。

Tests the full flow: message in → FeishuBotHandler → OrchestratorAgent → card out.
Uses a mock orchestrator to validate the complete wiring.
"""

from __future__ import annotations

import asyncio
import pytest

from integrations.feishu_bot import (
    FeishuBotHandler,
    FeishuCardResponse,
    FeishuMessage,
    _format_result,
)


# ---------------------------------------------------------------------------
# Mock orchestrator for E2E testing
# ---------------------------------------------------------------------------

class MockOrchestrator:
    """Simulates OrchestratorAgent for E2E testing."""

    def __init__(self):
        self.requests: list[str] = []

    async def handle_request(self, text: str) -> dict:
        self.requests.append(text)
        return {
            "status": "completed",
            "result": f"Processed: {text}",
            "agent": "mock_orchestrator",
        }


class FailOrchestrator:
    """Orchestrator that always raises."""

    async def handle_request(self, text: str) -> dict:
        raise RuntimeError("Simulated failure")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# E2E: Full message flow with mock orchestrator
# ===========================================================================

class TestFeishuE2EFlow:
    def setup_method(self):
        self.mock_orch = MockOrchestrator()
        self.handler = FeishuBotHandler(orchestrator=self.mock_orch)

    def test_free_text_routes_to_orchestrator(self):
        msg = FeishuMessage(text="检查今天水平衡", user_id="u1")
        resp = _run(self.handler.handle_message(msg))
        assert isinstance(resp, FeishuCardResponse)
        assert resp.status == "success"
        assert "Processed:" in resp.content
        assert len(self.mock_orch.requests) == 1

    def test_command_routes_to_orchestrator(self):
        msg = FeishuMessage(text="/水平衡 今日全厂", user_id="u1")
        resp = _run(self.handler.handle_message(msg))
        assert resp.status == "success"
        assert len(self.mock_orch.requests) == 1
        assert "water_balance" in self.mock_orch.requests[0]

    def test_forecast_command(self):
        msg = FeishuMessage(text="/预报 未来三天水位", user_id="u2")
        resp = _run(self.handler.handle_message(msg))
        assert resp.status == "success"
        assert "forecast" in self.mock_orch.requests[0]

    def test_warning_command(self):
        msg = FeishuMessage(text="/预警", user_id="u3")
        resp = _run(self.handler.handle_message(msg))
        assert resp.status == "success"
        assert "warning" in self.mock_orch.requests[0]

    def test_leak_command(self):
        msg = FeishuMessage(text="/泄漏", user_id="u4")
        resp = _run(self.handler.handle_message(msg))
        assert resp.status == "success"
        assert "leak_diagnosis" in self.mock_orch.requests[0]

    def test_dispatch_command(self):
        msg = FeishuMessage(text="/调度 全局优化", user_id="u5")
        resp = _run(self.handler.handle_message(msg))
        assert resp.status == "success"
        assert "global_dispatch" in self.mock_orch.requests[0]

    def test_daily_report_command(self):
        msg = FeishuMessage(text="/日报", user_id="u6")
        resp = _run(self.handler.handle_message(msg))
        assert resp.status == "success"
        assert "daily_report" in self.mock_orch.requests[0]

    def test_evap_command(self):
        msg = FeishuMessage(text="/蒸发 冷却塔", user_id="u7")
        resp = _run(self.handler.handle_message(msg))
        assert resp.status == "success"
        assert "evap_optimization" in self.mock_orch.requests[0]

    def test_odd_command(self):
        msg = FeishuMessage(text="/ODD 全维度", user_id="u8")
        resp = _run(self.handler.handle_message(msg))
        assert resp.status == "success"
        assert "odd_check" in self.mock_orch.requests[0]

    def test_english_commands(self):
        for cmd, skill in [
            ("/balance", "water_balance"),
            ("/evap", "evap_optimization"),
            ("/leak", "leak_diagnosis"),
            ("/dispatch", "global_dispatch"),
            ("/report", "daily_report"),
        ]:
            orch = MockOrchestrator()
            handler = FeishuBotHandler(orchestrator=orch)
            msg = FeishuMessage(text=cmd, user_id="u9")
            resp = _run(handler.handle_message(msg))
            assert resp.status == "success"
            assert skill in orch.requests[0], f"{cmd} should route to {skill}"

    def test_multiple_messages_sequential(self):
        msgs = ["你好", "/水平衡", "分析今日蒸发", "/ODD 安全"]
        for text in msgs:
            msg = FeishuMessage(text=text, user_id="u1")
            resp = _run(self.handler.handle_message(msg))
            assert resp.status == "success"
        assert len(self.mock_orch.requests) == 4

    def test_card_response_format(self):
        msg = FeishuMessage(text="测试", user_id="u1")
        resp = _run(self.handler.handle_message(msg))
        card = resp.to_card_json()
        assert "header" in card
        assert "elements" in card
        assert card["header"]["template"] == "green"  # success = green


# ===========================================================================
# E2E: Error handling
# ===========================================================================

class TestFeishuE2EErrorHandling:
    def test_orchestrator_failure(self):
        handler = FeishuBotHandler(orchestrator=FailOrchestrator())
        msg = FeishuMessage(text="trigger error", user_id="u1")
        resp = _run(handler.handle_message(msg))
        assert resp.status == "error"
        assert "failed" in resp.content.lower()

    def test_command_failure(self):
        handler = FeishuBotHandler(orchestrator=FailOrchestrator())
        msg = FeishuMessage(text="/水平衡 test", user_id="u1")
        resp = _run(handler.handle_message(msg))
        assert resp.status == "error"


# ===========================================================================
# Webhook verification
# ===========================================================================

class TestFeishuWebhookVerification:
    def test_challenge_echo(self):
        handler = FeishuBotHandler()
        result = handler.verify_webhook({"challenge": "abc123"})
        assert result == {"challenge": "abc123"}

    def test_no_challenge(self):
        handler = FeishuBotHandler()
        result = handler.verify_webhook({"event": {"message": {}}})
        assert result is None

    def test_empty_body(self):
        handler = FeishuBotHandler()
        result = handler.verify_webhook({})
        assert result is None


# ===========================================================================
# Result formatting
# ===========================================================================

class TestFormatResult:
    def test_string_passthrough(self):
        assert _format_result("hello") == "hello"

    def test_dict_formatting(self):
        result = _format_result({"status": "ok", "value": 42})
        assert "**status**:" in result
        assert "42" in result

    def test_nested_dict(self):
        result = _format_result({"metrics": {"rmse": 0.1, "mae": 0.05}})
        assert "**metrics**:" in result
        assert "rmse" in result

    def test_list_value(self):
        result = _format_result({"items": [1, 2, 3]})
        assert "3 items" in result

    def test_non_dict_non_str(self):
        assert _format_result(42) == "42"


# ===========================================================================
# Singleton orchestrator injection
# ===========================================================================

class TestOrchestratorInjection:
    def test_injected_orchestrator_used(self):
        mock = MockOrchestrator()
        handler = FeishuBotHandler(orchestrator=mock)
        assert handler._get_orchestrator() is mock

    def test_no_injection_creates_new(self):
        handler = FeishuBotHandler()
        orch = handler._get_orchestrator()
        from agents.orchestrator import OrchestratorAgent
        assert isinstance(orch, OrchestratorAgent)
