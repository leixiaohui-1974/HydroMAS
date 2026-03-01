"""Tests for HydroClaw heartbeat service.
HydroClaw 心跳服务测试。
"""

import pytest

from hydroclaw.heartbeat.service import HeartbeatService, HeartbeatCheck, CheckStatus, HeartbeatResult


class TestHeartbeatCheck:
    """Test HeartbeatCheck dataclass."""

    def test_defaults(self):
        check = HeartbeatCheck(name="test", description="Test check")
        assert check.enabled is True
        assert check.interval_seconds == 3600
        assert check.last_run == 0.0


class TestHeartbeatResult:
    """Test HeartbeatResult dataclass."""

    def test_to_dict(self):
        result = HeartbeatResult(
            check_name="test",
            status=CheckStatus.OK,
            message="All good",
            details={"metric": 42},
        )
        d = result.to_dict()
        assert d["check_name"] == "test"
        assert d["status"] == "ok"
        assert d["message"] == "All good"
        assert d["details"]["metric"] == 42


class TestHeartbeatService:
    """Test HeartbeatService."""

    @pytest.fixture
    def service(self):
        return HeartbeatService()

    def test_default_checks_registered(self, service):
        checks = service.get_all_checks()
        assert "system_health" in checks
        assert "odd_scan" in checks
        assert "water_balance" in checks
        assert "memory_consolidation" in checks
        assert "resource_monitor" in checks

    def test_register_custom_check(self, service):
        service.register_check("custom_check", "Custom test", interval_seconds=60)
        check = service.get_check("custom_check")
        assert check is not None
        assert check.interval_seconds == 60

    @pytest.mark.asyncio
    async def test_run_system_health(self, service):
        result = await service.run_check("system_health")
        assert result.check_name == "system_health"
        assert result.status in (CheckStatus.OK, CheckStatus.CRITICAL)

    @pytest.mark.asyncio
    async def test_run_resource_monitor(self, service):
        result = await service.run_check("resource_monitor")
        assert result.check_name == "resource_monitor"
        assert "disk_usage_pct" in result.details

    @pytest.mark.asyncio
    async def test_run_unknown_check(self, service):
        result = await service.run_check("nonexistent")
        assert result.status == CheckStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_run_all_due(self, service):
        # All checks are due (last_run=0)
        results = await service.run_all_due()
        assert len(results) >= 5

    @pytest.mark.asyncio
    async def test_run_all_due_respects_interval(self, service):
        # Run once
        await service.run_all_due()
        # Run again immediately — should not re-run
        results2 = await service.run_all_due()
        assert len(results2) == 0  # Nothing due yet

    def test_get_status_summary(self, service):
        summary = service.get_status_summary()
        assert "overall_status" in summary
        assert "checks" in summary
        assert "total_checks" in summary

    @pytest.mark.asyncio
    async def test_status_summary_after_checks(self, service):
        await service.run_check("system_health")
        summary = service.get_status_summary()
        assert summary["checks"]["system_health"]["status"] in ("ok", "critical", "warning")

    @pytest.mark.asyncio
    async def test_odd_scan(self, service):
        result = await service.run_check("odd_scan")
        assert result.check_name == "odd_scan"
        # May pass or warn depending on ODD config availability
        assert result.status in (CheckStatus.OK, CheckStatus.WARNING, CheckStatus.CRITICAL)

    @pytest.mark.asyncio
    async def test_water_balance_check(self, service):
        result = await service.run_check("water_balance")
        assert result.status == CheckStatus.OK

    @pytest.mark.asyncio
    async def test_memory_consolidation_check(self, service):
        result = await service.run_check("memory_consolidation")
        assert result.status == CheckStatus.OK
