"""AgentMessage — standardized inter-agent communication protocol.
AgentMessage — 标准化 Agent 间通信协议。

Defines message types, message format, and the async MessageBus
that enables publish-subscribe and request-response patterns
between agents.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message type definitions
# ---------------------------------------------------------------------------

class MessageType(str, Enum):
    """Types of inter-agent messages. / Agent 间消息类型。"""

    REQUEST = "request"       # Task/query request
    RESPONSE = "response"     # Response to a request
    EVENT = "event"           # Broadcast event notification
    ERROR = "error"           # Error report
    HEARTBEAT = "heartbeat"   # Agent liveness signal


class MessagePriority(int, Enum):
    """Message priority levels. / 消息优先级。"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


# ---------------------------------------------------------------------------
# AgentMessage dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentMessage:
    """Standard message exchanged between agents.
    Agent 间交换的标准消息。

    Attributes:
        id: Unique message identifier
        type: Message type (request/response/event/error)
        sender: ID of the sending agent
        recipient: ID of the target agent (or topic for events)
        content: Message payload
        correlation_id: Links response to original request
        priority: Message priority level
        metadata: Additional routing/tracing metadata
        timestamp: Unix timestamp of creation
    """

    type: MessageType
    sender: str
    recipient: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    correlation_id: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    # HydroClaw user context (v0.2.0)
    user_id: str = ""
    role: str = ""
    session_id: str = ""
    group: str = ""

    def reply(
        self,
        content: dict[str, Any],
        msg_type: MessageType = MessageType.RESPONSE,
    ) -> AgentMessage:
        """Create a reply message to this message.
        创建此消息的回复消息。
        """
        return AgentMessage(
            type=msg_type,
            sender=self.recipient,
            recipient=self.sender,
            content=content,
            correlation_id=self.id,
            priority=self.priority,
            metadata={"reply_to": self.id},
        )

    def error_reply(self, error: str) -> AgentMessage:
        """Create an error reply. / 创建错误回复。"""
        return AgentMessage(
            type=MessageType.ERROR,
            sender=self.recipient,
            recipient=self.sender,
            content={"error": error},
            correlation_id=self.id,
            priority=MessagePriority.HIGH,
            metadata={"reply_to": self.id},
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "correlation_id": self.correlation_id,
            "priority": self.priority.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


# Type alias for message handler callbacks
MessageHandler = Callable[[AgentMessage], Coroutine[Any, Any, AgentMessage | None]]


# ---------------------------------------------------------------------------
# MessageBus — async pub/sub + request/response
# ---------------------------------------------------------------------------

class MessageBus:
    """Async message bus for inter-agent communication.
    异步消息总线 — Agent 间通信枢纽。

    Supports:
        - Direct messaging (send to a specific agent)
        - Topic-based pub/sub (publish/subscribe events)
        - Request/response with correlation tracking
        - Message history for audit/tracing
    """

    def __init__(self, max_history: int = 1000):
        self._handlers: dict[str, MessageHandler] = {}
        self._topic_subscribers: dict[str, list[MessageHandler]] = defaultdict(list)
        self._pending_requests: dict[str, asyncio.Future[AgentMessage]] = {}
        self._history: list[AgentMessage] = []
        self._max_history = max_history

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_handler(self, agent_id: str, handler: MessageHandler) -> None:
        """Register a message handler for an agent.
        为 Agent 注册消息处理器。
        """
        self._handlers[agent_id] = handler
        logger.debug("MessageBus: registered handler for %s", agent_id)

    def unregister_handler(self, agent_id: str) -> None:
        """Remove an agent's message handler. / 移除 Agent 的消息处理器。"""
        self._handlers.pop(agent_id, None)

    # ------------------------------------------------------------------
    # Topic subscription
    # ------------------------------------------------------------------

    def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe a handler to a topic. / 订阅主题。"""
        self._topic_subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: MessageHandler) -> None:
        """Unsubscribe a handler from a topic. / 取消订阅。"""
        subs = self._topic_subscribers.get(topic, [])
        if handler in subs:
            subs.remove(handler)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def send(self, message: AgentMessage) -> AgentMessage | None:
        """Send a message to a specific agent (direct messaging).
        向特定 Agent 发送消息（直接消息传递）。

        For REQUEST messages, waits for and returns the response.
        For other types, delivers asynchronously and returns None.
        """
        self._record(message)

        handler = self._handlers.get(message.recipient)
        if handler is None:
            logger.warning(
                "MessageBus: no handler for recipient %s (msg %s)",
                message.recipient, message.id,
            )
            return message.error_reply(f"No handler registered for {message.recipient}")

        try:
            response = await handler(message)
            if response is not None:
                self._record(response)
            return response
        except Exception as exc:
            logger.error(
                "MessageBus: handler error for %s: %s",
                message.recipient, exc, exc_info=True,
            )
            return message.error_reply(str(exc))

    async def publish(self, topic: str, message: AgentMessage) -> list[AgentMessage]:
        """Publish an event message to all topic subscribers.
        向所有主题订阅者发布事件消息。

        Returns list of responses from subscribers.
        """
        self._record(message)
        subscribers = self._topic_subscribers.get(topic, [])
        if not subscribers:
            logger.debug("MessageBus: no subscribers for topic %s", topic)
            return []

        responses: list[AgentMessage] = []
        tasks = [sub(message) for sub in subscribers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error("MessageBus: subscriber error: %s", result)
            elif result is not None:
                self._record(result)
                responses.append(result)

        return responses

    async def request(
        self,
        message: AgentMessage,
        timeout: float = 30.0,
    ) -> AgentMessage:
        """Send a request and wait for the correlated response.
        发送请求并等待关联响应。

        This is a convenience wrapper around ``send`` for REQUEST messages.
        """
        if message.type != MessageType.REQUEST:
            message.type = MessageType.REQUEST

        response = await asyncio.wait_for(self.send(message), timeout=timeout)
        if response is None:
            return message.error_reply("No response received")
        return response

    # ------------------------------------------------------------------
    # History / audit
    # ------------------------------------------------------------------

    def get_history(
        self,
        agent_id: str | None = None,
        msg_type: MessageType | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get message history, optionally filtered.
        获取消息历史，可选过滤。
        """
        msgs = self._history
        if agent_id:
            msgs = [m for m in msgs if m.sender == agent_id or m.recipient == agent_id]
        if msg_type:
            msgs = [m for m in msgs if m.type == msg_type]
        return [m.to_dict() for m in msgs[-limit:]]

    def clear_history(self) -> None:
        """Clear message history. / 清空消息历史。"""
        self._history.clear()

    def _record(self, message: AgentMessage) -> None:
        """Record a message in history. / 记录消息到历史。"""
        self._history.append(message)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
