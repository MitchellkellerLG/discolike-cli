"""Tests for CacheManager — SQLite cache with TTL."""

from __future__ import annotations

from pathlib import Path

import pytest

from discolike.cache import CacheManager


@pytest.fixture
def cache(tmp_path: Path) -> CacheManager:
    """Create a CacheManager with a temp DB."""
    db = tmp_path / "test_cache.db"
    return CacheManager(db_path=db)


class TestCacheGetSet:
    def test_set_and_get(self, cache: CacheManager) -> None:
        cache.set("key1", "value1", "test")
        result = cache.get("key1", ttl=3600)
        assert result == "value1"

    def test_get_missing_key_returns_none(self, cache: CacheManager) -> None:
        result = cache.get("nonexistent", ttl=3600)
        assert result is None

    def test_ttl_expiry(self, cache: CacheManager) -> None:
        cache.set("expire_me", "data", "test")
        # Use a TTL of 0 so it's immediately expired
        result = cache.get("expire_me", ttl=0)
        assert result is None

    def test_ttl_not_expired(self, cache: CacheManager) -> None:
        cache.set("fresh", "data", "test")
        result = cache.get("fresh", ttl=9999)
        assert result == "data"

    def test_overwrite_key(self, cache: CacheManager) -> None:
        cache.set("key", "v1", "test")
        cache.set("key", "v2", "test")
        assert cache.get("key", ttl=3600) == "v2"

    def test_expired_entry_is_deleted(self, cache: CacheManager) -> None:
        cache.set("gone", "data", "test")
        # Expire it
        cache.get("gone", ttl=0)
        # Stats should show 0 entries
        stats = cache.stats()
        assert stats["total_entries"] == 0


class TestCacheClear:
    def test_clear_all(self, cache: CacheManager) -> None:
        cache.set("a", "1", "cat1")
        cache.set("b", "2", "cat2")
        removed = cache.clear()
        assert removed == 2
        assert cache.stats()["total_entries"] == 0

    def test_clear_by_category(self, cache: CacheManager) -> None:
        cache.set("a", "1", "keep")
        cache.set("b", "2", "remove")
        cache.set("c", "3", "remove")
        removed = cache.clear(category="remove")
        assert removed == 2
        stats = cache.stats()
        assert stats["total_entries"] == 1
        assert stats["by_category"]["keep"] == 1

    def test_clear_nonexistent_category(self, cache: CacheManager) -> None:
        cache.set("a", "1", "cat1")
        removed = cache.clear(category="nope")
        assert removed == 0
        assert cache.stats()["total_entries"] == 1


class TestCacheStats:
    def test_empty_stats(self, cache: CacheManager) -> None:
        stats = cache.stats()
        assert stats["total_entries"] == 0
        assert stats["by_category"] == {}

    def test_stats_by_category(self, cache: CacheManager) -> None:
        cache.set("a", "1", "extract")
        cache.set("b", "2", "extract")
        cache.set("c", "3", "profile")
        stats = cache.stats()
        assert stats["total_entries"] == 3
        assert stats["by_category"]["extract"] == 2
        assert stats["by_category"]["profile"] == 1

    def test_stats_includes_db_path(self, cache: CacheManager) -> None:
        stats = cache.stats()
        assert "db_path" in stats
        assert "test_cache.db" in stats["db_path"]


class TestCostPersistence:
    def test_record_and_retrieve_cost(self, cache: CacheManager) -> None:
        cache.record_cost(
            endpoint="discover",
            query_fee="0.18",
            record_fee="0.07",
            total="0.25",
            records_returned=20,
            plan="starter",
        )
        costs = cache.get_session_costs()
        assert len(costs) == 1
        assert costs[0]["endpoint"] == "discover"
        assert costs[0]["query_fee"] == "0.18"
        assert costs[0]["record_fee"] == "0.07"
        assert costs[0]["total"] == "0.25"
        assert costs[0]["records_returned"] == 20
        assert costs[0]["plan"] == "starter"
        assert "created_at" in costs[0]

    def test_session_total(self, cache: CacheManager) -> None:
        cache.record_cost("ep1", "0.10", "0.05", "0.15", 10, "starter")
        cache.record_cost("ep2", "0.10", "0.10", "0.20", 20, "starter")
        total = cache.get_session_total()
        assert float(total) == pytest.approx(0.35)

    def test_empty_session_total(self, cache: CacheManager) -> None:
        total = cache.get_session_total()
        assert float(total) == 0.0

    def test_reset_costs(self, cache: CacheManager) -> None:
        cache.record_cost("ep1", "0.10", "0.05", "0.15", 10, "starter")
        cache.record_cost("ep2", "0.10", "0.10", "0.20", 20, "starter")
        removed = cache.reset_costs()
        assert removed == 2
        assert cache.get_session_costs() == []
        assert float(cache.get_session_total()) == 0.0

    def test_multiple_costs_ordered(self, cache: CacheManager) -> None:
        cache.record_cost("first", "0.10", "0.00", "0.10", 0, "starter")
        cache.record_cost("second", "0.10", "0.00", "0.10", 0, "starter")
        cache.record_cost("third", "0.10", "0.00", "0.10", 0, "starter")
        costs = cache.get_session_costs()
        assert [c["endpoint"] for c in costs] == ["first", "second", "third"]


class TestTasksPersistence:
    def test_tasks_table_created_on_init(self, cache: CacheManager) -> None:
        """Tasks table exists in cache.db alongside cache and costs tables."""
        row = cache._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        assert row is not None
        assert row[0] == "tasks"

    def test_save_task_inserts_row(self, cache: CacheManager) -> None:
        cache.save_task("task-123", "discogen", '{"domains": ["x.com"]}')
        task = cache.get_task("task-123")
        assert task is not None
        assert task["task_id"] == "task-123"
        assert task["endpoint"] == "discogen"
        assert task["status"] == "in_progress"
        assert task["params_json"] == '{"domains": ["x.com"]}'
        assert task["submitted_at"] is not None

    def test_save_task_sets_submitted_at(self, cache: CacheManager) -> None:
        import time
        before = time.time()
        cache.save_task("task-ts", "discogen")
        after = time.time()
        task = cache.get_task("task-ts")
        assert task is not None
        assert before <= task["submitted_at"] <= after

    def test_save_task_replace_existing(self, cache: CacheManager) -> None:
        """INSERT OR REPLACE: saving same task_id replaces existing row."""
        cache.save_task("task-123", "discogen", '{"domains": ["x.com"]}')
        cache.save_task("task-123", "discogen", '{"domains": ["y.com"]}')
        task = cache.get_task("task-123")
        assert task is not None
        assert task["params_json"] == '{"domains": ["y.com"]}'

    def test_get_task_missing_returns_none(self, cache: CacheManager) -> None:
        result = cache.get_task("nonexistent")
        assert result is None

    def test_get_task_has_all_keys(self, cache: CacheManager) -> None:
        cache.save_task("task-keys", "discogen")
        task = cache.get_task("task-keys")
        assert task is not None
        expected_keys = {
            "task_id", "endpoint", "status", "submitted_at",
            "last_polled_at", "params_json", "error_message",
        }
        assert set(task.keys()) == expected_keys

    def test_update_task_status_sets_status(self, cache: CacheManager) -> None:
        cache.save_task("task-upd", "discogen")
        cache.update_task_status("task-upd", "completed")
        task = cache.get_task("task-upd")
        assert task is not None
        assert task["status"] == "completed"

    def test_update_task_status_sets_last_polled_at(self, cache: CacheManager) -> None:
        import time
        cache.save_task("task-poll", "discogen")
        before = time.time()
        cache.update_task_status("task-poll", "completed")
        after = time.time()
        task = cache.get_task("task-poll")
        assert task is not None
        assert before <= task["last_polled_at"] <= after

    def test_update_task_status_sets_error_message(self, cache: CacheManager) -> None:
        cache.save_task("task-err", "discogen")
        cache.update_task_status("task-err", "failed", "Server error")
        task = cache.get_task("task-err")
        assert task is not None
        assert task["status"] == "failed"
        assert task["error_message"] == "Server error"

    def test_list_tasks_returns_all(self, cache: CacheManager) -> None:
        cache.save_task("t1", "discogen")
        cache.save_task("t2", "validate/icp")
        cache.save_task("t3", "segment")
        tasks = cache.list_tasks()
        assert len(tasks) == 3

    def test_list_tasks_status_filter_matching(self, cache: CacheManager) -> None:
        cache.save_task("t1", "discogen")
        cache.save_task("t2", "validate/icp")
        cache.update_task_status("t2", "completed")
        in_progress = cache.list_tasks(status_filter="in_progress")
        assert len(in_progress) == 1
        assert in_progress[0]["task_id"] == "t1"

    def test_list_tasks_status_filter_nonexistent(self, cache: CacheManager) -> None:
        cache.save_task("t1", "discogen")
        result = cache.list_tasks(status_filter="nonexistent")
        assert result == []

    def test_list_tasks_empty(self, cache: CacheManager) -> None:
        result = cache.list_tasks()
        assert result == []


class TestCacheClose:
    def test_close(self, tmp_path: Path) -> None:
        db = tmp_path / "close_test.db"
        cm = CacheManager(db_path=db)
        cm.set("key", "value", "test")
        cm.close()
        # Re-opening should still see the data (persisted to disk)
        cm2 = CacheManager(db_path=db)
        assert cm2.get("key", ttl=3600) == "value"
        cm2.close()
