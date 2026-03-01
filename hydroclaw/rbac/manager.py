"""RBACManager — role-based access control for skills and API endpoints.
RBAC 管理器 — 基于角色的技能和 API 端点权限控制。

Permission model:
- Each role has a set of allowed skills and API categories
- Skills can be "execute" (run) or "read" (view results only)
- API categories map to cognitive layers: perception, cognition, decision, control
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Permission(Enum):
    """Permission levels for skills and APIs."""
    DENIED = "denied"
    READ = "read"       # Can view results but not trigger
    EXECUTE = "execute"  # Can trigger and view


@dataclass
class Role:
    """A role definition with allowed capabilities."""
    name: str
    name_cn: str
    description: str
    # Skill permissions: skill_name → Permission
    skill_permissions: dict[str, Permission] = field(default_factory=dict)
    # API category permissions: category → Permission
    api_permissions: dict[str, Permission] = field(default_factory=dict)
    # Whether this role can issue control commands (PID/MPC/MRC)
    can_control: bool = False
    # Whether this role can modify system config
    can_admin: bool = False
    # Maximum concurrent requests
    max_concurrent: int = 4


# ---- Default role definitions ----

_PERCEPTION_SKILLS = [
    "forecast_skill", "water_balance", "leak_diagnosis",
]
_COGNITION_SKILLS = [
    "warning_skill", "four_prediction_loop", "odd_assessment",
    "daily_report", "data_analysis_predict",
]
_DECISION_SKILLS = [
    "rehearsal_skill", "plan_skill", "global_dispatch",
    "reuse_scheduling", "evap_optimization", "optimization_design",
]
_CONTROL_SKILLS = [
    "control_system_design",
]
_RESEARCH_SKILLS = [
    "full_lifecycle", "collaborative_dev", "content_pipeline",
]

DEFAULT_ROLES: dict[str, Role] = {
    "operator": Role(
        name="operator",
        name_cn="运维助理",
        description="实时监控、调度控制、四预系统、安全监测、日报生成",
        skill_permissions={
            **{s: Permission.EXECUTE for s in _PERCEPTION_SKILLS},
            **{s: Permission.EXECUTE for s in _COGNITION_SKILLS},
            **{s: Permission.EXECUTE for s in _DECISION_SKILLS},
            "control_system_design": Permission.READ,
            "collaborative_dev": Permission.DENIED,
            "content_pipeline": Permission.DENIED,
        },
        api_permissions={
            "perception": Permission.EXECUTE,
            "cognition": Permission.EXECUTE,
            "decision": Permission.EXECUTE,
            "control": Permission.EXECUTE,
            "data": Permission.EXECUTE,
        },
        can_control=True,
    ),
    "designer": Role(
        name="designer",
        name_cn="设计助理",
        description="控制设计、优化设计、敏感性分析、方案比选",
        skill_permissions={
            **{s: Permission.EXECUTE for s in _PERCEPTION_SKILLS},
            **{s: Permission.EXECUTE for s in _COGNITION_SKILLS},
            **{s: Permission.EXECUTE for s in _DECISION_SKILLS},
            "control_system_design": Permission.EXECUTE,
            "collaborative_dev": Permission.DENIED,
            "content_pipeline": Permission.DENIED,
        },
        api_permissions={
            "perception": Permission.EXECUTE,
            "cognition": Permission.EXECUTE,
            "decision": Permission.EXECUTE,
            "control": Permission.EXECUTE,
            "data": Permission.EXECUTE,
        },
        can_control=True,
    ),
    "researcher": Role(
        name="researcher",
        name_cn="科研助理",
        description="仿真建模、数据分析、文献检索、论文写作辅助",
        skill_permissions={
            **{s: Permission.EXECUTE for s in _PERCEPTION_SKILLS},
            **{s: Permission.EXECUTE for s in _COGNITION_SKILLS},
            **{s: Permission.READ for s in _DECISION_SKILLS},
            "control_system_design": Permission.READ,
            "full_lifecycle": Permission.EXECUTE,
            "content_pipeline": Permission.EXECUTE,
            "collaborative_dev": Permission.READ,
        },
        api_permissions={
            "perception": Permission.EXECUTE,
            "cognition": Permission.EXECUTE,
            "decision": Permission.READ,
            "control": Permission.READ,
            "data": Permission.EXECUTE,
        },
        can_control=False,
    ),
    "admin": Role(
        name="admin",
        name_cn="管理员",
        description="全功能访问，系统配置与管理",
        skill_permissions={
            **{s: Permission.EXECUTE for s in _PERCEPTION_SKILLS},
            **{s: Permission.EXECUTE for s in _COGNITION_SKILLS},
            **{s: Permission.EXECUTE for s in _DECISION_SKILLS},
            **{s: Permission.EXECUTE for s in _CONTROL_SKILLS},
            **{s: Permission.EXECUTE for s in _RESEARCH_SKILLS},
        },
        api_permissions={
            "perception": Permission.EXECUTE,
            "cognition": Permission.EXECUTE,
            "decision": Permission.EXECUTE,
            "control": Permission.EXECUTE,
            "data": Permission.EXECUTE,
            "admin": Permission.EXECUTE,
        },
        can_control=True,
        can_admin=True,
    ),
    "teacher": Role(
        name="teacher",
        name_cn="教学助理",
        description="教学场景、原理演示、实验指导、受控仿真",
        skill_permissions={
            **{s: Permission.EXECUTE for s in _PERCEPTION_SKILLS},
            **{s: Permission.EXECUTE for s in _COGNITION_SKILLS},
            "rehearsal_skill": Permission.EXECUTE,
            "plan_skill": Permission.READ,
            "global_dispatch": Permission.READ,
            "control_system_design": Permission.EXECUTE,
            "optimization_design": Permission.EXECUTE,
            "full_lifecycle": Permission.EXECUTE,
            "collaborative_dev": Permission.DENIED,
            "content_pipeline": Permission.DENIED,
        },
        api_permissions={
            "perception": Permission.EXECUTE,
            "cognition": Permission.EXECUTE,
            "decision": Permission.READ,
            "control": Permission.READ,
            "data": Permission.EXECUTE,
        },
        can_control=False,
    ),
}


class RBACManager:
    """Role-Based Access Control manager.

    Usage:
        rbac = RBACManager()
        if rbac.check_skill("operator", "global_dispatch"):
            # Execute skill
        else:
            # Deny access
    """

    def __init__(self, roles: dict[str, Role] | None = None):
        self._roles = roles or dict(DEFAULT_ROLES)

    def get_role(self, role_name: str) -> Role | None:
        return self._roles.get(role_name)

    def get_all_roles(self) -> dict[str, Role]:
        return dict(self._roles)

    def check_skill(self, role_name: str, skill_name: str) -> bool:
        """Check if role can execute a skill."""
        role = self._roles.get(role_name)
        if not role:
            return False
        perm = role.skill_permissions.get(skill_name, Permission.DENIED)
        return perm == Permission.EXECUTE

    def check_skill_read(self, role_name: str, skill_name: str) -> bool:
        """Check if role can at least read skill results."""
        role = self._roles.get(role_name)
        if not role:
            return False
        perm = role.skill_permissions.get(skill_name, Permission.DENIED)
        return perm in (Permission.READ, Permission.EXECUTE)

    def check_api(self, role_name: str, category: str) -> bool:
        """Check if role can access an API category."""
        role = self._roles.get(role_name)
        if not role:
            return False
        perm = role.api_permissions.get(category, Permission.DENIED)
        return perm == Permission.EXECUTE

    def check_control(self, role_name: str) -> bool:
        """Check if role can issue control commands."""
        role = self._roles.get(role_name)
        return role.can_control if role else False

    def check_admin(self, role_name: str) -> bool:
        """Check if role has admin privileges."""
        role = self._roles.get(role_name)
        return role.can_admin if role else False

    def get_allowed_skills(self, role_name: str) -> list[str]:
        """List all skills this role can execute."""
        role = self._roles.get(role_name)
        if not role:
            return []
        return [
            name for name, perm in role.skill_permissions.items()
            if perm == Permission.EXECUTE
        ]

    def get_role_summary(self, role_name: str) -> dict:
        """Get a summary of a role's permissions."""
        role = self._roles.get(role_name)
        if not role:
            return {"error": f"Unknown role: {role_name}"}
        return {
            "name": role.name,
            "name_cn": role.name_cn,
            "description": role.description,
            "can_control": role.can_control,
            "can_admin": role.can_admin,
            "allowed_skills": self.get_allowed_skills(role_name),
            "api_categories": {
                cat: perm.value for cat, perm in role.api_permissions.items()
            },
        }
