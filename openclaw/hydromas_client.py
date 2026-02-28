"""HydroMAS API Client — for OpenClaw skill integration.
HydroMAS API 客户端 — 供 OpenClaw 技能调用。

This module provides a Python client SDK that OpenClaw skills can use
to call HydroMAS gateway API endpoints. Designed to run inside the
OpenClaw agent runtime on the same server or remote.

Usage in OpenClaw skill:
    from hydromas_client import HydroMASClient

    client = HydroMASClient("http://localhost:8000")
    result = client.chat("检查今天水平衡", role="operator")
    result = client.run_skill("daily_report", {"date": "2026-02-28"})
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8000"
_TIMEOUT = 60  # seconds


@dataclass
class HydroMASResponse:
    """Response from HydroMAS API. / HydroMAS API 响应。"""

    success: bool = False
    status: str = ""
    data: dict = field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0

    def to_markdown(self) -> str:
        """Format response as Markdown for OpenClaw display."""
        if not self.success:
            return f"**Error**: {self.error}"
        return _dict_to_markdown(self.data)


class HydroMASClient:
    """HTTP client for HydroMAS gateway API.
    HydroMAS 网关 API 的 HTTP 客户端。

    Uses only stdlib (urllib) to avoid dependency on requests/httpx,
    so it can be dropped into any OpenClaw skill without extra deps.
    """

    def __init__(self, base_url: str = _DEFAULT_BASE_URL, timeout: int = _TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Core gateway methods
    # ------------------------------------------------------------------

    def chat(
        self,
        message: str,
        role: str = "operator",
        session_id: str = "",
        params: dict | None = None,
    ) -> HydroMASResponse:
        """Send a natural language message to HydroMAS.
        发送自然语言消息到 HydroMAS。

        Args:
            message: User input text
            role: researcher | designer | operator
            session_id: Optional session tracking ID
            params: Additional parameters
        """
        return self._post("/api/gateway/chat", {
            "message": message,
            "role": role,
            "session_id": session_id,
            "params": params or {},
        })

    def run_skill(self, skill_name: str, params: dict | None = None) -> HydroMASResponse:
        """Execute a named skill on HydroMAS.
        在 HydroMAS 上执行指定技能。
        """
        return self._post("/api/gateway/skill", {
            "skill_name": skill_name,
            "params": params or {},
        })

    def get_roles(self) -> HydroMASResponse:
        """Get available assistant roles.
        获取可用助理角色。
        """
        return self._get("/api/gateway/roles")

    def get_role_actions(self, role: str) -> HydroMASResponse:
        """Get quick actions for a role.
        获取角色快捷操作。
        """
        return self._get(f"/api/gateway/roles/{role}/actions")

    def get_skills(self, role: str | None = None) -> HydroMASResponse:
        """List available skills, optionally filtered by role.
        列出可用技能。
        """
        path = "/api/gateway/skills"
        if role:
            path += f"?role={role}"
        return self._get(path)

    def health_check(self) -> HydroMASResponse:
        """Check HydroMAS health.
        检查 HydroMAS 健康状态。
        """
        return self._get("/api/gateway/health")

    # ------------------------------------------------------------------
    # Domain-specific convenience methods
    # ------------------------------------------------------------------

    def forecast(self, params: dict | None = None) -> HydroMASResponse:
        """Run water level forecast. / 运行水位预报。"""
        return self.run_skill("forecast_skill", params)

    def warning(self, params: dict | None = None) -> HydroMASResponse:
        """Run early warning analysis. / 运行预警分析。"""
        return self.run_skill("warning_skill", params)

    def daily_report(self, date: str = "") -> HydroMASResponse:
        """Generate daily operations report. / 生成日运营报告。"""
        return self.run_skill("daily_report", {"date": date} if date else {})

    def leak_diagnosis(self, params: dict | None = None) -> HydroMASResponse:
        """Run leak detection and diagnosis. / 运行泄漏检测。"""
        return self.run_skill("leak_diagnosis", params)

    def water_balance(self, params: dict | None = None) -> HydroMASResponse:
        """Run water balance calculation. / 运行水平衡核算。"""
        return self.chat("执行全厂水平衡核算", role="operator", params=params)

    def odd_check(self, params: dict | None = None) -> HydroMASResponse:
        """Run ODD safety check. / 运行ODD安全检查。"""
        return self.run_skill("odd_assessment", params)

    def global_dispatch(self, params: dict | None = None) -> HydroMASResponse:
        """Run global water dispatch optimization. / 运行全局调度优化。"""
        return self.run_skill("global_dispatch", params)

    # ------------------------------------------------------------------
    # HTTP helpers (stdlib only — no external deps)
    # ------------------------------------------------------------------

    def _post(self, path: str, body: dict) -> HydroMASResponse:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._do_request(req)

    def _get(self, path: str) -> HydroMASResponse:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        return self._do_request(req)

    def _do_request(self, req: urllib.request.Request) -> HydroMASResponse:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return HydroMASResponse(
                    success=True,
                    status=body.get("status", "ok"),
                    data=body,
                )
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            logger.error("HydroMAS API error %d: %s", exc.code, error_body[:200])
            return HydroMASResponse(
                success=False,
                status="error",
                error=f"HTTP {exc.code}: {error_body[:200]}",
            )
        except urllib.error.URLError as exc:
            logger.error("HydroMAS connection error: %s", exc.reason)
            return HydroMASResponse(
                success=False,
                status="connection_error",
                error=f"Connection failed: {exc.reason}",
            )
        except Exception as exc:
            logger.error("HydroMAS client error: %s", exc)
            return HydroMASResponse(
                success=False,
                status="error",
                error=str(exc),
            )


def _dict_to_markdown(d: dict, indent: int = 0) -> str:
    """Convert a nested dict to readable Markdown."""
    lines = []
    prefix = "  " * indent
    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}**{key}**:")
            lines.append(_dict_to_markdown(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}**{key}**: {len(value)} items")
            for item in value[:5]:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  - {json.dumps(item, ensure_ascii=False)[:100]}")
                else:
                    lines.append(f"{prefix}  - {item}")
            if len(value) > 5:
                lines.append(f"{prefix}  - ... ({len(value) - 5} more)")
        else:
            lines.append(f"{prefix}**{key}**: {value}")
    return "\n".join(lines)
