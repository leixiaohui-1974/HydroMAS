"""Tests for HydroClaw personality system.
HydroClaw 人格系统测试。
"""

import tempfile
from pathlib import Path

import pytest

from hydroclaw.personality.manager import PersonalityManager, PersonalityProfile


@pytest.fixture
def personality_dir(tmp_path):
    """Create a temporary personality directory with test files."""
    # Create SOUL.md
    (tmp_path / "SOUL.md").write_text(
        "# SOUL.md\n我是小瀚，水网智能助手。\n## 认知能力\n- 感知：数字孪生\n",
        encoding="utf-8",
    )

    # Create IDENTITY.md
    (tmp_path / "IDENTITY.md").write_text(
        "**Name:** 小瀚\n**Emoji:** 🌊\n**Role:** 水网助手\n",
        encoding="utf-8",
    )

    # Create group USER.md files
    admin_dir = tmp_path / "groups" / "admin"
    admin_dir.mkdir(parents=True)
    (admin_dir / "USER.md").write_text(
        "# 管理组\n角色：admin\n完整权限。\n",
        encoding="utf-8",
    )

    student_dir = tmp_path / "groups" / "student-a"
    student_dir.mkdir(parents=True)
    (student_dir / "USER.md").write_text(
        "# 学生A组\n角色：teacher\n教学场景。\n",
        encoding="utf-8",
    )

    return tmp_path


class TestPersonalityProfile:
    """Test PersonalityProfile dataclass."""

    def test_default_agent_name(self):
        profile = PersonalityProfile()
        assert profile.agent_name == "小瀚"

    def test_custom_agent_name(self):
        profile = PersonalityProfile(identity="**Name:** 测试助手\n**Emoji:** 🔧")
        assert profile.agent_name == "测试助手"

    def test_agent_emoji(self):
        profile = PersonalityProfile(identity="**Name:** Test\nemoji: 🌊")
        assert profile.agent_emoji == "🌊"

    def test_default_emoji(self):
        profile = PersonalityProfile()
        assert profile.agent_emoji == "🌊"

    def test_system_prompt_generation(self):
        profile = PersonalityProfile(
            soul="I am the soul.",
            identity="I am the identity.",
            user="User context.",
        )
        prompt = profile.get_system_prompt()
        assert "I am the soul." in prompt
        assert "I am the identity." in prompt
        assert "User context." in prompt


class TestPersonalityManager:
    """Test PersonalityManager."""

    def test_load_profile_with_soul(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        profile = mgr.load_profile()
        assert "小瀚" in profile.soul
        assert "水网智能助手" in profile.soul

    def test_load_profile_with_identity(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        profile = mgr.load_profile()
        assert "小瀚" in profile.identity

    def test_load_admin_group(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        profile = mgr.load_profile(group="admin")
        assert "管理组" in profile.user
        assert "admin" in profile.user

    def test_load_student_group(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        profile = mgr.load_profile(group="student-a")
        assert "学生A组" in profile.user

    def test_load_unknown_group(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        profile = mgr.load_profile(group="nonexistent")
        # Should still load soul and identity, but user is empty
        assert "小瀚" in profile.soul
        assert profile.user == ""

    def test_get_all_groups(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        groups = mgr.get_all_groups()
        assert "admin" in groups
        assert "student-a" in groups

    def test_update_user_profile(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        mgr.update_user_profile("user123", "# Custom\nCustom user profile.")
        profile = mgr.load_profile(user_id="user123")
        assert "Custom user profile." in profile.user

    def test_cache_invalidation(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        # Load and cache
        profile1 = mgr.load_profile(group="admin", user_id="u1")
        assert "管理组" in profile1.user

        # Update user override
        mgr.update_user_profile("u1", "# Override\nNew profile.")
        profile2 = mgr.load_profile(group="admin", user_id="u1")
        assert "New profile." in profile2.user

    def test_clear_cache(self, personality_dir):
        mgr = PersonalityManager(personality_dir)
        mgr.load_profile(group="admin")
        assert len(mgr._cache) > 0
        mgr.clear_cache()
        assert len(mgr._cache) == 0

    def test_empty_personality_dir(self, tmp_path):
        mgr = PersonalityManager(tmp_path)
        profile = mgr.load_profile()
        assert profile.soul == ""
        assert profile.identity == ""
        assert profile.user == ""
