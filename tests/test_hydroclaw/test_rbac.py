"""Tests for HydroClaw RBAC system.
HydroClaw 权限控制测试。
"""

import pytest

from hydroclaw.rbac.manager import RBACManager, Role, Permission, DEFAULT_ROLES


class TestPermission:
    """Test Permission enum."""

    def test_values(self):
        assert Permission.DENIED.value == "denied"
        assert Permission.READ.value == "read"
        assert Permission.EXECUTE.value == "execute"


class TestRBACManager:
    """Test RBACManager."""

    @pytest.fixture
    def rbac(self):
        return RBACManager()

    def test_get_role(self, rbac):
        role = rbac.get_role("operator")
        assert role is not None
        assert role.name == "operator"
        assert role.name_cn == "运维助理"

    def test_get_all_roles(self, rbac):
        roles = rbac.get_all_roles()
        assert len(roles) == 5
        assert set(roles.keys()) == {"operator", "designer", "researcher", "admin", "teacher"}

    def test_unknown_role(self, rbac):
        assert rbac.get_role("unknown") is None

    # -- Operator role --

    def test_operator_can_execute_forecast(self, rbac):
        assert rbac.check_skill("operator", "forecast_skill")

    def test_operator_can_execute_dispatch(self, rbac):
        assert rbac.check_skill("operator", "global_dispatch")

    def test_operator_cannot_execute_collab_dev(self, rbac):
        assert not rbac.check_skill("operator", "collaborative_dev")

    def test_operator_can_control(self, rbac):
        assert rbac.check_control("operator")

    def test_operator_cannot_admin(self, rbac):
        assert not rbac.check_admin("operator")

    # -- Designer role --

    def test_designer_can_execute_control_design(self, rbac):
        assert rbac.check_skill("designer", "control_system_design")

    def test_designer_can_control(self, rbac):
        assert rbac.check_control("designer")

    # -- Researcher role --

    def test_researcher_can_read_dispatch(self, rbac):
        assert rbac.check_skill_read("researcher", "global_dispatch")

    def test_researcher_cannot_execute_dispatch(self, rbac):
        assert not rbac.check_skill("researcher", "global_dispatch")

    def test_researcher_can_execute_full_lifecycle(self, rbac):
        assert rbac.check_skill("researcher", "full_lifecycle")

    def test_researcher_cannot_control(self, rbac):
        assert not rbac.check_control("researcher")

    # -- Admin role --

    def test_admin_can_execute_all(self, rbac):
        admin_skills = rbac.get_allowed_skills("admin")
        assert "forecast_skill" in admin_skills
        assert "global_dispatch" in admin_skills
        assert "control_system_design" in admin_skills
        assert "collaborative_dev" in admin_skills

    def test_admin_can_control(self, rbac):
        assert rbac.check_control("admin")

    def test_admin_can_admin(self, rbac):
        assert rbac.check_admin("admin")

    # -- Teacher role --

    def test_teacher_can_simulate(self, rbac):
        assert rbac.check_skill("teacher", "forecast_skill")

    def test_teacher_cannot_control(self, rbac):
        assert not rbac.check_control("teacher")

    def test_teacher_cannot_collab_dev(self, rbac):
        assert not rbac.check_skill("teacher", "collaborative_dev")

    # -- API permissions --

    def test_operator_api_perception(self, rbac):
        assert rbac.check_api("operator", "perception")

    def test_researcher_api_control_read_only(self, rbac):
        assert not rbac.check_api("researcher", "control")

    def test_admin_api_all(self, rbac):
        assert rbac.check_api("admin", "perception")
        assert rbac.check_api("admin", "cognition")
        assert rbac.check_api("admin", "decision")
        assert rbac.check_api("admin", "control")
        assert rbac.check_api("admin", "admin")

    # -- Role summary --

    def test_role_summary(self, rbac):
        summary = rbac.get_role_summary("operator")
        assert summary["name"] == "operator"
        assert summary["name_cn"] == "运维助理"
        assert summary["can_control"] is True
        assert len(summary["allowed_skills"]) > 0

    def test_unknown_role_summary(self, rbac):
        summary = rbac.get_role_summary("unknown")
        assert "error" in summary

    # -- Custom roles --

    def test_custom_roles(self):
        custom_roles = {
            "custom": Role(
                name="custom",
                name_cn="自定义",
                description="Custom role",
                skill_permissions={"forecast_skill": Permission.EXECUTE},
            ),
        }
        rbac = RBACManager(roles=custom_roles)
        assert rbac.check_skill("custom", "forecast_skill")
        assert not rbac.check_skill("custom", "global_dispatch")
