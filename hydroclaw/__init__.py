"""Legacy HydroClaw compatibility package for HydroMAS runtime.

The canonical package identity now moves toward ``hydromas`` while
``hydroclaw`` remains as a backwards-compatible import surface.

核心模块：
- personality: SOUL/USER/IDENTITY 人格系统
- memory: 长期记忆 + 每日笔记 + 交互日志
- session: 多用户会话隔离
- rbac: 角色权限控制（5种角色）
- heartbeat: 主动巡检与推送
- evolution: 自进化数据采集与分析
"""

__version__ = "0.3.0"
__all__ = [
    "PersonalityManager",
    "MemoryManager",
    "SessionManager",
    "RBACManager",
    "HeartbeatService",
    "InteractionLogger",
    "EvolutionAnalyzer",
]
