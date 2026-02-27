"""AgentRegistry — central registry for agent discovery and management.
AgentRegistry — Agent 发现与管理的中央注册表。

Provides capability-based routing, agent lifecycle management,
and integration with the MessageBus for automatic handler registration.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agents.base_agent import AgentCard, AgentStatus, BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Central registry for all HydroMAS agents.
    HydroMAS 所有 Agent 的中央注册表。

    Responsibilities:
        - Register / deregister agent instances
        - Discover agents by capability, name, or type
        - Load agent cards from JSON files
        - Connect agents to the MessageBus
        - Manage agent lifecycle (initialize / shutdown)
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._cards: dict[str, AgentCard] = {}
        self._message_bus: Any | None = None  # set via connect_bus()

    # ------------------------------------------------------------------
    # Bus integration
    # ------------------------------------------------------------------

    def connect_bus(self, bus: Any) -> None:
        """Connect the registry to a MessageBus.
        将注册表连接到 MessageBus。

        Already-registered agents will be wired to the bus.
        """
        self._message_bus = bus
        for agent_id, agent in self._agents.items():
            agent._message_bus = bus
            bus.register_handler(agent_id, agent.handle_message)
        logger.info("Registry connected to MessageBus (%d agents wired)", len(self._agents))

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, agent: BaseAgent) -> None:
        """Register an agent instance.
        注册 Agent 实例。

        If a MessageBus is connected, also wires the agent's handler.
        """
        agent_id = agent.agent_id
        if agent_id in self._agents:
            logger.warning("Agent %s already registered — replacing", agent_id)
        self._agents[agent_id] = agent

        if agent.card:
            self._cards[agent_id] = agent.card

        if self._message_bus is not None:
            agent._message_bus = self._message_bus
            self._message_bus.register_handler(agent_id, agent.handle_message)

        logger.info(
            "Registered agent %s (%s) with %d capabilities",
            agent_id, agent.__class__.__name__,
            len(agent.get_capabilities()),
        )

    def deregister(self, agent_id: str) -> None:
        """Remove an agent from the registry.
        从注册表中移除 Agent。
        """
        agent = self._agents.pop(agent_id, None)
        self._cards.pop(agent_id, None)
        if agent and self._message_bus:
            self._message_bus.unregister_handler(agent_id)
        logger.info("Deregistered agent %s", agent_id)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        """Get an agent by its ID. / 根据 ID 获取 Agent。"""
        return self._agents.get(agent_id)

    def get_all_agents(self) -> dict[str, BaseAgent]:
        """Get all registered agents. / 获取所有已注册 Agent。"""
        return dict(self._agents)

    def find_by_capability(self, capability: str) -> list[BaseAgent]:
        """Find agents that provide a specific capability.
        查找提供特定能力的 Agent。

        Args:
            capability: Capability string to search for

        Returns:
            List of agents with the requested capability.
        """
        return [
            agent for agent in self._agents.values()
            if capability in agent.get_capabilities()
        ]

    def find_by_type(self, agent_type: type) -> list[BaseAgent]:
        """Find agents of a specific class type.
        查找特定类型的 Agent。
        """
        return [
            agent for agent in self._agents.values()
            if isinstance(agent, agent_type)
        ]

    def find_by_status(self, status: AgentStatus) -> list[BaseAgent]:
        """Find agents with a specific status. / 按状态查找 Agent。"""
        return [
            agent for agent in self._agents.values()
            if agent.status == status
        ]

    # ------------------------------------------------------------------
    # Agent card management
    # ------------------------------------------------------------------

    def load_cards(self, cards_dir: str | Path) -> dict[str, AgentCard]:
        """Load all agent cards from a directory.
        从目录加载所有 Agent 卡片。

        Args:
            cards_dir: Path to directory containing *.json card files

        Returns:
            Dict of loaded cards keyed by agent name.
        """
        cards_dir = Path(cards_dir)
        loaded: dict[str, AgentCard] = {}
        for json_file in cards_dir.glob("*.json"):
            try:
                card = AgentCard.from_json(json_file)
                loaded[card.name] = card
                logger.debug("Loaded agent card: %s from %s", card.name, json_file)
            except Exception as e:
                logger.warning("Failed to load agent card from %s: %s", json_file, e)
        return loaded

    def get_card(self, agent_id: str) -> AgentCard | None:
        """Get the card for a registered agent. / 获取已注册 Agent 的卡片。"""
        return self._cards.get(agent_id)

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    async def initialize_all(self) -> None:
        """Initialize all registered agents.
        初始化所有已注册 Agent。
        """
        for agent_id, agent in self._agents.items():
            try:
                await agent.initialize()
                logger.info("Initialized agent %s", agent_id)
            except Exception as e:
                logger.error("Failed to initialize agent %s: %s", agent_id, e)
                agent.status = AgentStatus.ERROR

    async def shutdown_all(self) -> None:
        """Shutdown all registered agents.
        关闭所有已注册 Agent。
        """
        for agent_id, agent in self._agents.items():
            try:
                await agent.shutdown()
            except Exception as e:
                logger.error("Error shutting down agent %s: %s", agent_id, e)

    # ------------------------------------------------------------------
    # Summary / introspection
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Get a summary of all registered agents.
        获取所有已注册 Agent 的摘要。
        """
        agents_info = []
        for agent_id, agent in self._agents.items():
            agents_info.append({
                "id": agent_id,
                "type": agent.__class__.__name__,
                "status": agent.status.value,
                "capabilities": agent.get_capabilities(),
                "has_card": agent_id in self._cards,
            })
        return {
            "total_agents": len(self._agents),
            "agents": agents_info,
            "bus_connected": self._message_bus is not None,
        }
