"""Feishu HTTP Client — token management, retries, signature verification.
飞书 HTTP 客户端 — 令牌管理、重试、签名验证。

Provides a shared async HTTP client for all Feishu integrations:
- Tenant access token management (auto-refresh)
- Webhook signature verification (SHA256 HMAC)
- Retry with exponential backoff
- Unified error handling

Usage:
    client = FeishuClient(app_id="cli_xxx", app_secret="xxx")
    await client.post_webhook("https://...", payload)
    await client.post_api("/open-apis/bitable/v1/...", data)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Feishu Open API base URL
FEISHU_API_BASE = "https://open.feishu.cn"
TOKEN_URL = f"{FEISHU_API_BASE}/open-apis/auth/v3/tenant_access_token/internal"


@dataclass
class FeishuResponse:
    """Response from Feishu API call."""

    ok: bool = True
    code: int = 0
    msg: str = ""
    data: dict = field(default_factory=dict)
    http_status: int = 200

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "code": self.code,
            "msg": self.msg,
            "data": self.data,
            "http_status": self.http_status,
        }


class FeishuClient:
    """Shared HTTP client for Feishu Open Platform.
    飞书开放平台共享 HTTP 客户端。

    Features:
    - Tenant access token with auto-refresh (2h TTL, refreshes at 10min margin)
    - Webhook signature verification
    - Retry with exponential backoff (1s, 2s, 4s)
    - stdlib-only (no requests/httpx dependency)
    """

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        verification_token: str = "",
        encrypt_key: str = "",
        timeout: int = 10,
        max_retries: int = 3,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.encrypt_key = encrypt_key
        self.timeout = timeout
        self.max_retries = max_retries

        # Token cache
        self._tenant_token: str = ""
        self._token_expires_at: float = 0

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def get_tenant_token(self) -> str:
        """Get tenant access token, refreshing if expired.
        获取 tenant_access_token，过期自动刷新。
        """
        now = time.time()
        if self._tenant_token and now < self._token_expires_at:
            return self._tenant_token

        if not self.app_id or not self.app_secret:
            logger.warning("FeishuClient: app_id/app_secret not configured")
            return ""

        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }

        try:
            resp = self._http_post(TOKEN_URL, payload, auth=False)
            if resp.code == 0 and resp.data.get("tenant_access_token"):
                self._tenant_token = resp.data["tenant_access_token"]
                expire = resp.data.get("expire", 7200)
                # Refresh 10 minutes before expiry
                self._token_expires_at = now + expire - 600
                logger.info(
                    "FeishuClient: token refreshed, expires in %ds", expire,
                )
                return self._tenant_token
            else:
                logger.error(
                    "FeishuClient: token request failed: code=%d msg=%s",
                    resp.code, resp.msg,
                )
                return ""
        except Exception as exc:
            logger.error("FeishuClient: token request error: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Webhook signature verification
    # ------------------------------------------------------------------

    def verify_signature(self, timestamp: str, nonce: str, body: str, signature: str) -> bool:
        """Verify Feishu webhook callback signature.
        验证飞书回调签名。

        Feishu uses: SHA256(timestamp + nonce + encrypt_key + body)
        """
        if not self.encrypt_key:
            # No encrypt key configured → skip verification
            return True

        content = f"{timestamp}{nonce}{self.encrypt_key}{body}"
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_token(self, token: str) -> bool:
        """Verify the verification token from Feishu event subscription.
        验证飞书事件订阅的 verification token。
        """
        if not self.verification_token:
            return True
        return hmac.compare_digest(self.verification_token, token)

    # ------------------------------------------------------------------
    # HTTP methods
    # ------------------------------------------------------------------

    def post_webhook(self, webhook_url: str, payload: dict) -> FeishuResponse:
        """POST to a Feishu webhook (bot/alert group webhook).
        发送消息到飞书 Webhook（机器人/告警群 Webhook）。

        Webhooks don't need auth tokens.
        """
        if not webhook_url:
            return FeishuResponse(ok=False, code=-1, msg="webhook_url not configured")
        return self._http_post(webhook_url, payload, auth=False)

    def post_api(self, path: str, data: dict) -> FeishuResponse:
        """POST to a Feishu Open API endpoint (with auth).
        发送请求到飞书开放平台 API（带认证）。

        Args:
            path: API path, e.g. "/open-apis/bitable/v1/apps/:app_token/tables/:table_id/records"
            data: Request body
        """
        url = f"{FEISHU_API_BASE}{path}" if path.startswith("/") else path
        return self._http_post(url, data, auth=True)

    def get_api(self, path: str, params: dict | None = None) -> FeishuResponse:
        """GET from a Feishu Open API endpoint (with auth).
        从飞书开放平台 API 读取数据（带认证）。
        """
        url = f"{FEISHU_API_BASE}{path}" if path.startswith("/") else path
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"
        return self._http_get(url, auth=True)

    def send_message(self, receive_id: str, msg_type: str, content: dict,
                     receive_id_type: str = "chat_id") -> FeishuResponse:
        """Send a message via Feishu Open API.
        通过飞书开放平台 API 发送消息。
        """
        path = "/open-apis/im/v1/messages"
        data = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content) if isinstance(content, dict) else content,
        }
        url = f"{FEISHU_API_BASE}{path}?receive_id_type={receive_id_type}"
        return self._http_post(url, data, auth=True)

    def reply_message(self, message_id: str, msg_type: str, content: dict) -> FeishuResponse:
        """Reply to a message via Feishu Open API.
        通过飞书开放平台 API 回复消息。
        """
        path = f"/open-apis/im/v1/messages/{message_id}/reply"
        data = {
            "msg_type": msg_type,
            "content": json.dumps(content) if isinstance(content, dict) else content,
        }
        return self._http_post(f"{FEISHU_API_BASE}{path}", data, auth=True)

    # ------------------------------------------------------------------
    # Bitable API helpers
    # ------------------------------------------------------------------

    def bitable_create_record(
        self, app_token: str, table_id: str, fields: dict,
    ) -> FeishuResponse:
        """Create a record in Feishu Bitable.
        在飞书多维表格中创建记录。
        """
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        return self.post_api(path, {"fields": fields})

    def bitable_batch_create(
        self, app_token: str, table_id: str, records: list[dict],
    ) -> FeishuResponse:
        """Batch create records in Feishu Bitable.
        批量创建多维表格记录。
        """
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        return self.post_api(path, {"records": [{"fields": r} for r in records]})

    # ------------------------------------------------------------------
    # Internal HTTP helpers (stdlib-based, with retry)
    # ------------------------------------------------------------------

    def _http_post(self, url: str, data: dict, *, auth: bool = False) -> FeishuResponse:
        """POST with retry and exponential backoff."""
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if auth:
            token = self.get_tenant_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"

        body = json.dumps(data).encode("utf-8")

        for attempt in range(self.max_retries):
            try:
                req = Request(url, data=body, headers=headers, method="POST")
                with urlopen(req, timeout=self.timeout) as resp:
                    resp_body = resp.read().decode("utf-8")
                    result = json.loads(resp_body) if resp_body else {}
                    return FeishuResponse(
                        ok=result.get("code", 0) == 0,
                        code=result.get("code", 0),
                        msg=result.get("msg", ""),
                        data=result.get("data", result),
                        http_status=resp.status,
                    )
            except HTTPError as exc:
                resp_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
                logger.warning(
                    "FeishuClient POST %s attempt %d/%d: HTTP %d: %s",
                    url, attempt + 1, self.max_retries, exc.code, resp_body[:200],
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s
                else:
                    return FeishuResponse(
                        ok=False, code=exc.code,
                        msg=f"HTTP {exc.code}: {resp_body[:200]}",
                        http_status=exc.code,
                    )
            except URLError as exc:
                logger.warning(
                    "FeishuClient POST %s attempt %d/%d: %s",
                    url, attempt + 1, self.max_retries, exc.reason,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return FeishuResponse(
                        ok=False, code=-1,
                        msg=f"Network error: {exc.reason}",
                    )
            except Exception as exc:
                logger.error("FeishuClient POST %s unexpected error: %s", url, exc)
                return FeishuResponse(ok=False, code=-1, msg=str(exc))

        return FeishuResponse(ok=False, code=-1, msg="Max retries exceeded")

    def _http_get(self, url: str, *, auth: bool = False) -> FeishuResponse:
        """GET with retry and exponential backoff."""
        headers = {}
        if auth:
            token = self.get_tenant_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"

        for attempt in range(self.max_retries):
            try:
                req = Request(url, headers=headers, method="GET")
                with urlopen(req, timeout=self.timeout) as resp:
                    resp_body = resp.read().decode("utf-8")
                    result = json.loads(resp_body) if resp_body else {}
                    return FeishuResponse(
                        ok=result.get("code", 0) == 0,
                        code=result.get("code", 0),
                        msg=result.get("msg", ""),
                        data=result.get("data", result),
                        http_status=resp.status,
                    )
            except HTTPError as exc:
                resp_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
                logger.warning(
                    "FeishuClient GET %s attempt %d/%d: HTTP %d",
                    url, attempt + 1, self.max_retries, exc.code,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return FeishuResponse(
                        ok=False, code=exc.code,
                        msg=f"HTTP {exc.code}: {resp_body[:200]}",
                        http_status=exc.code,
                    )
            except URLError as exc:
                logger.warning(
                    "FeishuClient GET %s attempt %d/%d: %s",
                    url, attempt + 1, self.max_retries, exc.reason,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return FeishuResponse(
                        ok=False, code=-1,
                        msg=f"Network error: {exc.reason}",
                    )
            except Exception as exc:
                logger.error("FeishuClient GET %s unexpected error: %s", url, exc)
                return FeishuResponse(ok=False, code=-1, msg=str(exc))

        return FeishuResponse(ok=False, code=-1, msg="Max retries exceeded")
