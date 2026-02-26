"""Base Skill class for fixed workflow orchestration.
Skill 基类 — 固定工作流编排。

Each Skill is a verified, immutable workflow that chains MCP Tools
in a predetermined sequence. Agents cannot modify Skill internals;
they can only select which Skill to invoke and what parameters to pass.
"""

from __future__ import annotations

import importlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Result returned by a Skill execution.
    Skill 执行返回的结果。
    """

    success: bool = True
    data: dict = field(default_factory=dict)
    error: str | None = None
    execution_time: float = 0.0
    steps_completed: list[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass
class SkillMetadata:
    """Metadata loaded from Skill YAML file.
    从 YAML 文件加载的 Skill 元数据。
    """

    name: str
    display_name: str
    description: str
    trigger_phrases: list[str]
    input_schema: dict
    output_schema: dict
    tools_required: list[str]
    max_execution_time: int = 120

    @classmethod
    def from_yaml(cls, path: str | Path) -> SkillMetadata:
        """Load metadata from YAML file. / 从 YAML 加载元数据。"""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            description=data.get("description", ""),
            trigger_phrases=data.get("trigger_phrases", []),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            tools_required=data.get("tools_required", []),
            max_execution_time=data.get("max_execution_time", 120),
        )


class BaseSkill(ABC):
    """Abstract base class for all Skills.
    所有 Skill 的抽象基类。

    Subclasses must implement execute() with fixed workflow logic.
    Agent cannot modify execute() — it is a verified, immutable pipeline.
    """

    def __init__(self, metadata: SkillMetadata | None = None):
        self.metadata = metadata
        self._tool_registry: dict[str, Any] = {}

    def register_tool(self, name: str, tool_fn: Any) -> None:
        """Register a tool function for use within this Skill.
        注册 Skill 内部使用的工具函数。
        """
        self._tool_registry[name] = tool_fn

    async def call_tool(self, tool_name: str, params: dict) -> Any:
        """Call a registered MCP tool by name.
        按名称调用已注册的 MCP 工具。

        Args:
            tool_name: Name of the MCP tool / 工具名称
            params: Parameters to pass / 传递的参数

        Returns:
            Tool result.
        """
        import asyncio

        if tool_name in self._tool_registry:
            fn = self._tool_registry[tool_name]
            return await asyncio.to_thread(fn, **params)

        # Try dynamic import from mcp_servers (run in thread to avoid blocking)
        return await asyncio.to_thread(self._call_tool_dynamic, tool_name, params)

    def _call_tool_dynamic(self, tool_name: str, params: dict) -> Any:
        """Dynamically import and call a tool from mcp_servers.
        动态导入并调用 mcp_servers 中的工具。
        """
        tool_module_map = {
            "simulate_tank": ("mcp_servers.simulation_server", "simulate_tank"),
            "simulate_batch": ("mcp_servers.simulation_server", "simulate_batch"),
            "identify_parameters": ("mcp_servers.identification_server", "identify_parameters"),
            "clean_timeseries": ("mcp_servers.dataclean_server", "clean_timeseries"),
            "detect_outliers": ("mcp_servers.dataclean_server", "detect_outliers"),
            "predict_future": ("mcp_servers.prediction_server", "predict_future"),
            "optimize_schedule": ("mcp_servers.scheduling_server", "optimize_schedule"),
            "run_controller": ("mcp_servers.control_server", "run_controller"),
            "check_odd": ("mcp_servers.odd_server", "check_odd"),
            "get_mrc_plan": ("mcp_servers.odd_server", "get_mrc_plan"),
            "evaluate_performance": ("mcp_servers.evaluation_server", "evaluate_performance"),
            "assess_wnal": ("mcp_servers.evaluation_server", "assess_wnal"),
            "optimize_design": ("mcp_servers.design_server", "optimize_design"),
            "run_sensitivity": ("mcp_servers.design_server", "run_sensitivity"),
        }

        if tool_name not in tool_module_map:
            raise ValueError(f"Unknown tool: {tool_name}")

        module_path, fn_name = tool_module_map[tool_name]
        module = importlib.import_module(module_path)
        fn = getattr(module, fn_name)
        return fn(**params)

    async def run(self, params: dict) -> SkillResult:
        """Run the Skill with timing and error handling.
        运行 Skill，带计时和错误处理。

        Args:
            params: Skill input parameters / Skill 输入参数

        Returns:
            SkillResult with data or error.
        """
        start_time = time.time()
        try:
            result = await self.execute(params)
            result.execution_time = time.time() - start_time
            return result
        except Exception as e:
            logger.exception(f"Skill {self.__class__.__name__} failed")
            return SkillResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    @abstractmethod
    async def execute(self, params: dict) -> SkillResult:
        """Execute the Skill's fixed workflow.
        执行 Skill 的固定工作流。

        This method must be implemented by each Skill subclass.
        It defines the immutable sequence of tool calls.

        Args:
            params: Input parameters matching input_schema / 输入参数

        Returns:
            SkillResult with workflow outputs.
        """
        ...


def discover_skills(skills_dir: str | Path | None = None) -> dict[str, SkillMetadata]:
    """Discover all Skills by scanning YAML files in the skills directory.
    通过扫描 skills 目录中的 YAML 文件发现所有 Skill。

    Args:
        skills_dir: Path to skills directory / skills 目录路径

    Returns:
        Dict of {skill_name: SkillMetadata}.
    """
    if skills_dir is None:
        skills_dir = Path(__file__).parent

    skills_dir = Path(skills_dir)
    discovered = {}

    for yaml_file in skills_dir.glob("*.yaml"):
        try:
            meta = SkillMetadata.from_yaml(yaml_file)
            discovered[meta.name] = meta
            logger.info(f"Discovered skill: {meta.name}")
        except Exception as e:
            logger.warning(f"Failed to load skill from {yaml_file}: {e}")

    return discovered
