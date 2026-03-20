"""Tests for the new hydromas compatibility import surface."""

from hydromas import __version__
from hydromas.heartbeat import HeartbeatService
from hydromas.memory import MemoryManager
from hydromas.personality import PersonalityManager
from hydromas.rbac import RBACManager
from hydromas.session import SessionManager


def test_hydromas_version_matches_project():
    assert __version__ == "0.3.0"


def test_hydromas_runtime_aliases_import():
    assert MemoryManager is not None
    assert PersonalityManager is not None
    assert SessionManager is not None
    assert RBACManager is not None
    assert HeartbeatService is not None
