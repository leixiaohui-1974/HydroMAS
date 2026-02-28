"""BaseAgent — abstract base class for all HydroMAS agents.
BaseAgent — HydroMAS 所有 Agent 的抽象基类。

Provides a unified lifecycle interface, agent card loading,
and integration with the multi-agent message bus and registry.

Every agent in the platform (domain, devops, content) inherits
from BaseAgent so that the orchestrator and executor can manage
them uniformly.
"""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent status lifecycle
# ---------------------------------------------------------------------------

class AgentStatus(str, Enum):
    """Agent lifecycle status. / Agent 生命周期状态。"""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


# ---------------------------------------------------------------------------
# Agent card (capability descriptor)
# ---------------------------------------------------------------------------

@dataclass
class AgentCard:
    """Structured capability descriptor loaded from JSON card files.
    从 JSON 卡片文件加载的结构化能力描述符。
    """

    name: str
    display_name: str = ""
    description: str = ""
    version: str = "0.1.0"
    capabilities: list[str] = field(default_factory=list)
    supported_intents: list[str] = field(default_factory=list)
    protocol: str = "A2A"
    endpoint: str = ""
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, path: str | Path) -> AgentCard:
        """Load agent card from JSON file. / 从 JSON 文件加载 Agent 卡片。"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            description=data.get("description", ""),
            version=data.get("version", "0.1.0"),
            capabilities=data.get("capabilities", []),
            supported_intents=data.get("supported_intents", []),
            protocol=data.get("protocol", "A2A"),
            endpoint=data.get("endpoint", ""),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "capabilities": self.capabilities,
            "supported_intents": self.supported_intents,
            "protocol": self.protocol,
            "endpoint": self.endpoint,
        }


# ---------------------------------------------------------------------------
# BaseAgent abstract class
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """Abstract base class for all HydroMAS agents.
    所有 HydroMAS Agent 的抽象基类。

    Lifecycle:
        1. __init__  — construct with optional card / config
        2. initialize()  — async setup (connect to bus, register, etc.)
        3. handle_message()  — process incoming AgentMessage
        4. shutdown()  — cleanup resources

    Subclasses MUST implement ``handle_message`` and ``get_capabilities``.
    """

    def __init__(
        self,
        agent_id: str | None = None,
        card: AgentCard | None = None,
        config: dict | None = None,
    ):
        self.agent_id: str = agent_id or f"{self.__class__.__name__}_{uuid.uuid4().hex[:8]}"
        self.card: AgentCard | None = card
        self.config: dict = config or {}
        self.status: AgentStatus = AgentStatus.IDLE
        self._message_bus: Any | None = None  # set by registry/bus

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Async initialization hook — called after construction.
        异步初始化钩子 — 构造后调用。

        Override to perform async setup (e.g. load models, connect to bus).
        """
        self.status = AgentStatus.IDLE
        logger.info("Agent %s (%s) initialized", self.agent_id, self.__class__.__name__)

    async def shutdown(self) -> None:
        """Graceful shutdown hook.
        优雅关闭钩子。
        """
        self.status = AgentStatus.STOPPED
        logger.info("Agent %s shut down", self.agent_id)

    # ------------------------------------------------------------------
    # Core abstract methods
    # ------------------------------------------------------------------

    @abstractmethod
    async def handle_message(self, message: "AgentMessage") -> "AgentMessage":
        """Process an incoming message and return a response.
        处理传入消息并返回响应。

        Args:
            message: Incoming AgentMessage / 传入的 AgentMessage

        Returns:
            Response AgentMessage.
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return the list of capabilities this agent provides.
        返回此 Agent 提供的能力列表。

        Used by the registry for capability-based routing.
        """
        ...

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    async def send_message(self, message: "AgentMessage") -> "AgentMessage | None":
        """Send a message via the message bus (if connected).
        通过消息总线发送消息（如果已连接）。
        """
        if self._message_bus is None:
            logger.warning("Agent %s has no message bus — cannot send", self.agent_id)
            return None
        return await self._message_bus.send(message)

    def get_card(self) -> AgentCard | None:
        """Return the agent card if loaded. / 返回已加载的 Agent 卡片。"""
        return self.card

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.agent_id} status={self.status.value}>"


# ---------------------------------------------------------------------------
# Lazy import guard (AgentMessage is defined in agents.message)
# ---------------------------------------------------------------------------

# Forward reference resolved at runtime; callers import AgentMessage from agents.message
if False:  # TYPE_CHECKING
    from agents.message import AgentMessage  # noqa: F401
