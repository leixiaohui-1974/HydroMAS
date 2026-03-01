"""Heartbeat service — proactive monitoring and health checks.
心跳服务 — 主动巡检与健康检查。

Inspired by OpenClaw's HEARTBEAT.md:
- Periodic system health checks
- Water network anomaly detection
- Proactive Feishu push notifications
- Memory consolidation triggers
"""

from hydroclaw.heartbeat.service import HeartbeatService, HeartbeatCheck

__all__ = ["HeartbeatService", "HeartbeatCheck"]
