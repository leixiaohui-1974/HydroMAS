"""HydroMAS runtime compatibility package.

This package provides the new import surface for the HydroMAS workbench
runtime while reusing the legacy ``hydroclaw`` implementation internally.
"""

from hydroclaw import __version__
from hydromas.personality import PersonalityManager
from hydromas.memory import MemoryManager
from hydromas.session import SessionManager, Session
from hydromas.rbac import RBACManager
from hydromas.heartbeat import HeartbeatService
from hydromas.evolution import InteractionLogger, EvolutionAnalyzer

__all__ = [
    "PersonalityManager",
    "MemoryManager",
    "SessionManager",
    "Session",
    "RBACManager",
    "HeartbeatService",
    "InteractionLogger",
    "EvolutionAnalyzer",
]
