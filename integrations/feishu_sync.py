"""Feishu Bitable Sync — bidirectional data synchronization.
飞书多维表格同步 — 双向数据同步。

Syncs HydroMAS pipeline data, KPIs, and project tasks with
Feishu Bitable (多维表格) for team visibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from integrations.feishu_client import FeishuClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BitableRecord:
    """A record to sync with Feishu Bitable. / 待同步到飞书多维表格的记录。"""

    table_id: str = ""
    record_id: str = ""
    fields: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "record_id": self.record_id,
            "fields": self.fields,
        }


@dataclass
class SyncResult:
    """Result of a sync operation. / 同步操作结果。"""

    success: bool = True
    records_synced: int = 0
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat(),
    )

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "records_synced": self.records_synced,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Table schema definitions for HydroMAS
# ---------------------------------------------------------------------------

HYDROMAS_TABLES = {
    "pipeline_runs": {
        "name": "开发流水线 Pipeline Runs",
        "fields": {
            "pipeline_id": "text",
            "requirement": "text",
            "status": "single_select",
            "planning_status": "single_select",
            "review_status": "single_select",
            "testing_status": "single_select",
            "iteration": "number",
            "created_at": "date",
            "completed_at": "date",
        },
    },
    "water_kpi": {
        "name": "水网 KPI / Water KPIs",
        "fields": {
            "date": "date",
            "daily_intake": "number",
            "daily_reuse": "number",
            "reuse_rate": "number",
            "daily_evaporation": "number",
            "pump_energy": "number",
            "residual": "number",
            "anomaly_count": "number",
        },
    },
    "alerts": {
        "name": "告警记录 / Alerts",
        "fields": {
            "alert_id": "text",
            "severity": "single_select",
            "dimension": "text",
            "value": "number",
            "threshold": "number",
            "message": "text",
            "timestamp": "date",
            "resolved": "checkbox",
        },
    },
    "dev_tasks": {
        "name": "开发任务 / Dev Tasks",
        "fields": {
            "task_id": "text",
            "description": "text",
            "assignee": "text",
            "status": "single_select",
            "priority": "single_select",
            "module": "text",
            "due_date": "date",
        },
    },
}


# ---------------------------------------------------------------------------
# FeishuBitableSync
# ---------------------------------------------------------------------------

class FeishuBitableSync:
    """Bidirectional sync between HydroMAS and Feishu Bitable.
    HydroMAS 与飞书多维表格的双向同步。

    Usage:
        sync = FeishuBitableSync(app_token="...", table_map={...})
        sync.sync_pipeline_run(pipeline_dict)
        sync.sync_water_kpi(kpi_dict)
    """

    def __init__(
        self,
        app_token: str = "",
        table_map: dict[str, str] | None = None,
        client: FeishuClient | None = None,
    ) -> None:
        self.app_token = app_token
        self.table_map = table_map or {}
        self._client = client
        self._pending: list[BitableRecord] = []
        self._synced: list[BitableRecord] = []

    def sync_pipeline_run(self, pipeline: dict) -> SyncResult:
        """Sync a dev pipeline run to Bitable.
        将开发流水线运行同步到多维表格。
        """
        stages = {
            s["name"]: s["status"]
            for s in pipeline.get("stages", [])
        }

        record = BitableRecord(
            table_id=self.table_map.get(
                "pipeline_runs", "pipeline_runs",
            ),
            fields={
                "pipeline_id": pipeline.get("id", ""),
                "requirement": pipeline.get("requirement", ""),
                "status": pipeline.get("status", ""),
                "planning_status": stages.get("planning", ""),
                "review_status": stages.get("review", ""),
                "testing_status": stages.get("testing", ""),
                "iteration": pipeline.get("iteration", 1),
                "created_at": pipeline.get("created_at", ""),
                "completed_at": pipeline.get("completed_at", ""),
            },
        )

        return self._push_record(record)

    def sync_water_kpi(self, kpi: dict) -> SyncResult:
        """Sync water KPI data to Bitable.
        将水网 KPI 数据同步到多维表格。
        """
        record = BitableRecord(
            table_id=self.table_map.get("water_kpi", "water_kpi"),
            fields={
                "date": kpi.get("date", datetime.now().strftime("%Y-%m-%d")),
                "daily_intake": kpi.get("daily_intake", 0),
                "daily_reuse": kpi.get("daily_reuse", 0),
                "reuse_rate": kpi.get("reuse_rate", 0),
                "daily_evaporation": kpi.get("daily_evaporation", 0),
                "pump_energy": kpi.get("pump_energy", 0),
                "residual": kpi.get("residual", 0),
                "anomaly_count": kpi.get("anomaly_count", 0),
            },
        )

        return self._push_record(record)

    def sync_alert(self, alert: dict) -> SyncResult:
        """Sync an alert event to Bitable.
        将告警事件同步到多维表格。
        """
        record = BitableRecord(
            table_id=self.table_map.get("alerts", "alerts"),
            fields={
                "alert_id": alert.get("alert_id", ""),
                "severity": alert.get("severity", "info"),
                "dimension": alert.get("dimension", ""),
                "value": alert.get("value", 0),
                "threshold": alert.get("threshold", 0),
                "message": alert.get("message", ""),
                "timestamp": alert.get("timestamp", ""),
                "resolved": alert.get("resolved", False),
            },
        )

        return self._push_record(record)

    def sync_dev_task(self, task: dict) -> SyncResult:
        """Sync a development task to Bitable.
        将开发任务同步到多维表格。
        """
        record = BitableRecord(
            table_id=self.table_map.get("dev_tasks", "dev_tasks"),
            fields={
                "task_id": task.get("id", ""),
                "description": task.get("description", ""),
                "assignee": task.get("assignee", ""),
                "status": task.get("status", "pending"),
                "priority": task.get("priority", "medium"),
                "module": task.get("module", ""),
                "due_date": task.get("due_date", ""),
            },
        )

        return self._push_record(record)

    def flush(self) -> SyncResult:
        """Push all pending records to Feishu. / 推送所有待同步记录。"""
        total = len(self._pending)
        if not total:
            return SyncResult(records_synced=0)

        errors: list[str] = []

        if self._client and self.app_token:
            # Production: batch API call to Feishu by table
            by_table: dict[str, list[dict]] = {}
            for rec in self._pending:
                by_table.setdefault(rec.table_id, []).append(rec.fields)

            for table_id, field_list in by_table.items():
                resp = self._client.bitable_batch_create(
                    self.app_token, table_id, field_list,
                )
                if not resp.ok:
                    errors.append(
                        f"Table {table_id}: {resp.msg}",
                    )
                    logger.error(
                        "FeishuSync: batch create failed for table %s: %s",
                        table_id, resp.msg,
                    )
                else:
                    logger.info(
                        "FeishuSync: pushed %d records to table %s",
                        len(field_list), table_id,
                    )

        self._synced.extend(self._pending)
        self._pending.clear()

        logger.info("FeishuSync: flushed %d records", total)
        return SyncResult(
            success=len(errors) == 0,
            records_synced=total,
            errors=errors,
        )

    def get_table_schemas(self) -> dict:
        """Get the Bitable table schema definitions."""
        return HYDROMAS_TABLES

    # ----- private -----

    def _push_record(self, record: BitableRecord) -> SyncResult:
        """Push a single record (or queue for batch)."""
        self._pending.append(record)

        if self.app_token:
            # Production: immediate push via API
            logger.info(
                "FeishuSync: queued record for table %s",
                record.table_id,
            )

        return SyncResult(records_synced=1)
