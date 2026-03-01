"""Tests for HydroClaw memory system.
HydroClaw 记忆系统测试。
"""

from pathlib import Path

import pytest

from hydroclaw.memory.manager import MemoryManager


@pytest.fixture
def memory_dir(tmp_path):
    return tmp_path


class TestMemoryManager:
    """Test MemoryManager."""

    def test_get_empty_memory(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        assert mgr.get_memory("default") == ""

    def test_append_memory(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_memory("default", "水平衡残差偏高时应检查阀门A。")
        memory = mgr.get_memory("default")
        assert "水平衡残差偏高" in memory

    def test_update_memory(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_memory("default", "Old content.")
        mgr.update_memory("default", "# New Memory\nCompletely new content.")
        memory = mgr.get_memory("default")
        assert "Completely new content." in memory
        assert "Old content." not in memory

    def test_daily_note_append(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_daily_note("default", "用户查询了水平衡", user_id="user1")
        note = mgr.get_daily_note("default")
        assert "水平衡" in note
        assert "user:user1" in note

    def test_daily_note_specific_date(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_daily_note("default", "Test note", date="2026-02-28")
        note = mgr.get_daily_note("default", date="2026-02-28")
        assert "Test note" in note

    def test_list_daily_notes(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_daily_note("default", "Note 1", date="2026-02-27")
        mgr.append_daily_note("default", "Note 2", date="2026-02-28")
        mgr.append_daily_note("default", "Note 3", date="2026-03-01")
        dates = mgr.list_daily_notes("default")
        assert len(dates) == 3
        assert dates[0] == "2026-03-01"  # Newest first

    def test_search_keywords(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_memory("default", "## 水平衡\n节点A残差偏高，建议检查阀门。")
        mgr.append_memory("default", "## 蒸发优化\n冷却塔效率可提升10%。")

        results = mgr.search("default", "水平衡 残差")
        assert len(results) > 0
        assert "水平衡" in results[0].content

    def test_search_no_results(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_memory("default", "Some content about water.")
        results = mgr.search("default", "完全无关的搜索词xyz")
        assert len(results) == 0

    def test_search_daily_notes(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_daily_note("default", "### 查询\n用户问了水平衡情况")
        results = mgr.search("default", "水平衡")
        assert len(results) > 0

    def test_consolidate_empty(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        result = mgr.consolidate("default")
        assert result == ""

    def test_consolidate_with_notes(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_daily_note("default", "Day 1 note", date="2026-02-28")
        mgr.append_daily_note("default", "Day 2 note", date="2026-03-01")
        result = mgr.consolidate("default", days_back=7)
        assert "Day 1 note" in result or "Day 2 note" in result

    def test_group_isolation(self, memory_dir):
        mgr = MemoryManager(memory_dir)
        mgr.append_memory("group-a", "Group A memory.")
        mgr.append_memory("group-b", "Group B memory.")
        assert "Group A" in mgr.get_memory("group-a")
        assert "Group B" in mgr.get_memory("group-b")
        assert "Group B" not in mgr.get_memory("group-a")
