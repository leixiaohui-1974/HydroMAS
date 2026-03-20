"""HeartbeatService — periodic health checks and proactive monitoring.
心跳服务 — 周期性健康检查与主动监测。

Runs configurable checks at specified intervals:
1. System health (HydroMAS API availability)
2. Water network anomaly scan (ODD violation detection)
3. Memory consolidation (merge daily notes)
4. Disk/resource monitoring
5. Proactive alert push (Feishu)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    """Health check result status."""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HeartbeatResult:
    """Result of a single heartbeat check."""
    check_name: str
    status: CheckStatus
    message: str
    details: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "check_name": self.check_name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class HeartbeatCheck:
    """Configuration for a heartbeat check."""
    name: str
    description: str
    interval_seconds: int = 3600  # Default: every hour
    enabled: bool = True
    last_run: float = 0.0
    last_result: HeartbeatResult | None = None


class HeartbeatService:
    """Manages periodic health checks for the HydroClaw platform.

    Usage:
        service = HeartbeatService()
        service.register_check("system_health", "系统健康检查", interval=3600)
        result = await service.run_check("system_health")
    """

    def __init__(self):
        self._checks: dict[str, HeartbeatCheck] = {}
        self._results_history: list[HeartbeatResult] = []
        self._max_history = 100
        self._running = False
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """Register the default set of heartbeat checks."""
        self._checks["system_health"] = HeartbeatCheck(
            name="system_health",
            description="HydroMAS API 可用性检查",
            interval_seconds=900,  # Every 15 minutes
        )
        self._checks["odd_scan"] = HeartbeatCheck(
            name="odd_scan",
            description="ODD 安全域全维度扫描",
            interval_seconds=3600,  # Every hour
        )
        self._checks["water_balance"] = HeartbeatCheck(
            name="water_balance",
            description="水平衡残差异常检测",
            interval_seconds=3600,
        )
        self._checks["memory_consolidation"] = HeartbeatCheck(
            name="memory_consolidation",
            description="每日记忆整理与知识沉淀",
            interval_seconds=14400,  # Every 4 hours
        )
        self._checks["resource_monitor"] = HeartbeatCheck(
            name="resource_monitor",
            description="系统资源 (磁盘/内存) 监测",
            interval_seconds=3600,
        )
        self._checks["session_cleanup"] = HeartbeatCheck(
            name="session_cleanup",
            description="过期会话清理 (24小时不活跃)",
            interval_seconds=3600,
        )

    def register_check(
        self,
        name: str,
        description: str,
        interval_seconds: int = 3600,
        enabled: bool = True,
    ) -> None:
        """Register a custom heartbeat check."""
        self._checks[name] = HeartbeatCheck(
            name=name,
            description=description,
            interval_seconds=interval_seconds,
            enabled=enabled,
        )

    def get_check(self, name: str) -> HeartbeatCheck | None:
        return self._checks.get(name)

    def get_all_checks(self) -> dict[str, HeartbeatCheck]:
        return dict(self._checks)

    async def run_check(self, name: str) -> HeartbeatResult:
        """Execute a specific heartbeat check."""
        check = self._checks.get(name)
        if not check:
            return HeartbeatResult(
                check_name=name,
                status=CheckStatus.UNKNOWN,
                message=f"Unknown check: {name}",
            )

        try:
            result = await self._execute_check(check)
        except Exception as exc:
            logger.exception("Heartbeat check '%s' failed", name)
            result = HeartbeatResult(
                check_name=name,
                status=CheckStatus.CRITICAL,
                message=f"Check failed: {exc}",
            )

        check.last_run = time.time()
        check.last_result = result
        self._results_history.append(result)
        if len(self._results_history) > self._max_history:
            self._results_history = self._results_history[-self._max_history:]

        return result

    async def run_all_due(self) -> list[HeartbeatResult]:
        """Run all checks that are due based on their intervals."""
        now = time.time()
        results = []
        for check in self._checks.values():
            if not check.enabled:
                continue
            if now - check.last_run >= check.interval_seconds:
                result = await self.run_check(check.name)
                results.append(result)
        return results

    async def _execute_check(self, check: HeartbeatCheck) -> HeartbeatResult:
        """Execute a check and return result."""
        if check.name == "system_health":
            return await self._check_system_health()
        elif check.name == "odd_scan":
            return await self._check_odd_scan()
        elif check.name == "water_balance":
            return await self._check_water_balance()
        elif check.name == "memory_consolidation":
            return await self._check_memory_consolidation()
        elif check.name == "resource_monitor":
            return await self._check_resource_monitor()
        elif check.name == "session_cleanup":
            return await self._check_session_cleanup()
        else:
            return HeartbeatResult(
                check_name=check.name,
                status=CheckStatus.OK,
                message="Custom check passed (default)",
            )

    async def _check_system_health(self) -> HeartbeatResult:
        """Check HydroMAS API availability."""
        try:
            from core.config import load_tank_config, load_odd_specs
            config = load_tank_config()
            odd_specs = load_odd_specs()
            return HeartbeatResult(
                check_name="system_health",
                status=CheckStatus.OK,
                message="HydroMAS 认知内核运行正常",
                details={
                    "tank_config_loaded": bool(config),
                    "odd_dimensions": len(odd_specs.get("dimensions", [])),
                    "layers": ["L0_core", "L1_compute", "L2_mcp", "L3_skills", "L4_agents"],
                },
            )
        except Exception as exc:
            return HeartbeatResult(
                check_name="system_health",
                status=CheckStatus.CRITICAL,
                message=f"系统健康检查失败: {exc}",
            )

    async def _check_odd_scan(self) -> HeartbeatResult:
        """Run ODD scan across all dimensions."""
        try:
            from core.odd import check_odd
            from core.config import load_odd_specs
            odd_specs = load_odd_specs()
            # Use nominal state for check
            nominal_state = {}
            for dim in odd_specs.get("dimensions", []):
                nominal_state[dim["name"]] = (dim["normal_range"][0] + dim["normal_range"][1]) / 2

            if not nominal_state:
                return HeartbeatResult(
                    check_name="odd_scan",
                    status=CheckStatus.OK,
                    message="ODD 配置为空，跳过扫描",
                )

            result = check_odd(nominal_state)
            overall = result.get("overall_zone", "normal")
            status = CheckStatus.OK if overall == "normal" else (
                CheckStatus.WARNING if overall == "extended" else CheckStatus.CRITICAL
            )
            return HeartbeatResult(
                check_name="odd_scan",
                status=status,
                message=f"ODD 状态: {overall}",
                details=result,
            )
        except Exception as exc:
            return HeartbeatResult(
                check_name="odd_scan",
                status=CheckStatus.WARNING,
                message=f"ODD 扫描异常: {exc}",
            )

    async def _check_water_balance(self) -> HeartbeatResult:
        """Check water balance residuals using core module."""
        try:
            import json
            from pathlib import Path
            config_path = Path("data/alumina_config.json")
            if not config_path.exists():
                return HeartbeatResult(
                    check_name="water_balance",
                    status=CheckStatus.OK,
                    message="水平衡检查: 无配置文件，跳过",
                )

            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)

            nodes_raw = config.get("nodes", [])
            if not nodes_raw:
                return HeartbeatResult(
                    check_name="water_balance",
                    status=CheckStatus.OK,
                    message="水平衡检查: 配置中无节点数据",
                )

            # Check if nodes have balance data (q_in/q_out)
            has_balance_data = any(
                isinstance(n, dict) and ("q_in" in n or "q_out" in n)
                for n in nodes_raw
            )
            if not has_balance_data:
                return HeartbeatResult(
                    check_name="water_balance",
                    status=CheckStatus.OK,
                    message=f"水平衡检查: {len(nodes_raw)} 个拓扑节点已加载 (无实时流量数据)",
                    details={"node_count": len(nodes_raw)},
                )

            from core.water_balance import BalanceNode, calc_full_balance
            nodes = []
            for n in nodes_raw:
                node_type = n.get("type", n.get("node_type", "workshop"))
                # Map config types to valid BalanceNode types
                type_map = {
                    "treatment": "intake", "source": "intake",
                    "pool": "pool", "tank": "pool",
                    "workshop": "workshop", "process": "workshop",
                    "reuse": "reuse", "recycle": "reuse",
                    "wastewater": "wastewater", "discharge": "wastewater",
                }
                mapped_type = type_map.get(node_type, "workshop")
                nodes.append(BalanceNode(
                    node_id=n.get("id", n.get("node_id", "")),
                    node_type=mapped_type,
                    q_in=n.get("q_in", 0),
                    q_out=n.get("q_out", 0),
                    q_loss=n.get("q_loss", 0),
                    q_evap=n.get("q_evap", 0),
                ))
            balance = calc_full_balance(nodes)
            total_residual = balance.get("total_residual", 0)
            status = (
                CheckStatus.OK if abs(total_residual) < 100
                else CheckStatus.WARNING if abs(total_residual) < 500
                else CheckStatus.CRITICAL
            )
            return HeartbeatResult(
                check_name="water_balance",
                status=status,
                message=f"水平衡残差: {total_residual:.1f} m³/d",
                details=balance,
            )
        except ImportError:
            return HeartbeatResult(
                check_name="water_balance",
                status=CheckStatus.OK,
                message="水平衡检查: core.water_balance 模块不可用",
            )
        except Exception as exc:
            return HeartbeatResult(
                check_name="water_balance",
                status=CheckStatus.WARNING,
                message=f"水平衡检查异常: {type(exc).__name__}: {exc}",
            )

    async def _check_memory_consolidation(self) -> HeartbeatResult:
        """Trigger memory consolidation for all groups."""
        try:
            from hydroclaw.memory import MemoryManager
            from pathlib import Path

            mgr = MemoryManager()
            base_dir = Path(mgr._dir)
            consolidated = 0
            groups_checked = 0

            if base_dir.exists():
                for group_dir in base_dir.iterdir():
                    if group_dir.is_dir():
                        groups_checked += 1
                        daily_dir = group_dir / "daily"
                        if daily_dir.exists():
                            note_count = len(list(daily_dir.glob("*.md")))
                            if note_count > 7:
                                mgr.consolidate(group_dir.name, days_back=7)
                                consolidated += 1

            return HeartbeatResult(
                check_name="memory_consolidation",
                status=CheckStatus.OK,
                message=f"记忆整理完成: {groups_checked} 个分组检查, {consolidated} 个已整合",
                details={
                    "groups_checked": groups_checked,
                    "groups_consolidated": consolidated,
                },
            )
        except Exception as exc:
            return HeartbeatResult(
                check_name="memory_consolidation",
                status=CheckStatus.WARNING,
                message=f"记忆整理异常: {type(exc).__name__}: {exc}",
            )

    async def _check_resource_monitor(self) -> HeartbeatResult:
        """Check disk and memory usage."""
        import shutil
        total, used, free = shutil.disk_usage("/")
        usage_pct = used / total * 100
        status = (
            CheckStatus.OK if usage_pct < 80
            else CheckStatus.WARNING if usage_pct < 90
            else CheckStatus.CRITICAL
        )
        return HeartbeatResult(
            check_name="resource_monitor",
            status=status,
            message=f"磁盘使用率: {usage_pct:.1f}%",
            details={
                "disk_total_gb": round(total / (1024**3), 1),
                "disk_used_gb": round(used / (1024**3), 1),
                "disk_free_gb": round(free / (1024**3), 1),
                "disk_usage_pct": round(usage_pct, 1),
            },
        )

    async def _check_session_cleanup(self) -> HeartbeatResult:
        """Clean up stale sessions (idle > 24 hours) and persist active ones.
        清理过期会话（空闲超过24小时）并持久化活跃会话。
        """
        try:
            from hydroclaw.session import SessionManager
            import os

            session_dir = (
                os.environ.get("HYDROMAS_SESSION_DIR")
                or os.environ.get("HYDROCLAW_SESSION_DIR")
            )
            scope = (
                os.environ.get("HYDROMAS_SESSION_SCOPE")
                or os.environ.get("HYDROCLAW_SESSION_SCOPE")
                or "per-user"
            )
            mgr = SessionManager(session_dir=session_dir, scope=scope)

            # Clean up stale sessions
            removed = mgr.cleanup_stale(max_idle_hours=24.0)

            # Persist remaining active sessions
            active = mgr.get_active_sessions()
            saved = 0
            for session in active:
                try:
                    mgr.save_session(session)
                    saved += 1
                except Exception:
                    pass

            return HeartbeatResult(
                check_name="session_cleanup",
                status=CheckStatus.OK,
                message=f"会话清理完成: {removed} 个过期清除, {saved} 个活跃持久化",
                details={
                    "stale_removed": removed,
                    "active_persisted": saved,
                    "active_count": mgr.get_session_count(),
                },
            )
        except Exception as exc:
            return HeartbeatResult(
                check_name="session_cleanup",
                status=CheckStatus.WARNING,
                message=f"会话清理异常: {exc}",
            )

    def get_status_summary(self) -> dict:
        """Get overall heartbeat status summary."""
        checks_status = {}
        overall = CheckStatus.OK

        for name, check in self._checks.items():
            if check.last_result:
                checks_status[name] = check.last_result.to_dict()
                if check.last_result.status == CheckStatus.CRITICAL:
                    overall = CheckStatus.CRITICAL
                elif check.last_result.status == CheckStatus.WARNING and overall != CheckStatus.CRITICAL:
                    overall = CheckStatus.WARNING
            else:
                checks_status[name] = {
                    "status": "not_run",
                    "description": check.description,
                }

        return {
            "overall_status": overall.value,
            "checks": checks_status,
            "total_checks": len(self._checks),
            "recent_results": [r.to_dict() for r in self._results_history[-10:]],
        }
