"""RED tests for Issue #10: CacheManager split into DataCache, CostLog, TaskStore.

The intent: CacheManager mixes three unrelated responsibilities.
Extracting them makes each testable in isolation and keeps public API per class < 5 methods.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from discolike.cache import CacheManager, DataCache, CostLog, TaskStore


# ---------------------------------------------------------------------------
# DataCache — TTL key/value store
# ---------------------------------------------------------------------------


@pytest.fixture
def data_cache(tmp_path: Path) -> DataCache:
    return DataCache(db_path=tmp_path / "data.db")


class TestDataCache:
    def test_set_and_get(self, data_cache: DataCache) -> None:
        data_cache.set("k", "v", "cat")
        assert data_cache.get("k", ttl=3600) == "v"

    def test_ttl_expiry(self, data_cache: DataCache) -> None:
        data_cache.set("k", "v", "cat")
        assert data_cache.get("k", ttl=0) is None

    def test_clear_by_category(self, data_cache: DataCache) -> None:
        data_cache.set("a", "1", "keep")
        data_cache.set("b", "2", "remove")
        removed = data_cache.clear(category="remove")
        assert removed == 1

    def test_stats(self, data_cache: DataCache) -> None:
        data_cache.set("a", "1", "cat")
        stats = data_cache.stats()
        assert stats["total_entries"] == 1


# ---------------------------------------------------------------------------
# CostLog — append-only cost ledger
# ---------------------------------------------------------------------------


@pytest.fixture
def cost_log(tmp_path: Path) -> CostLog:
    return CostLog(db_path=tmp_path / "cost.db")


class TestCostLog:
    def test_record_and_retrieve(self, cost_log: CostLog) -> None:
        cost_log.record("discover", "0.10", "0.05", "0.15", 10, "starter")
        entries = cost_log.entries()
        assert len(entries) == 1
        assert entries[0]["endpoint"] == "discover"

    def test_total(self, cost_log: CostLog) -> None:
        cost_log.record("ep1", "0.10", "0.05", "0.15", 10, "starter")
        cost_log.record("ep2", "0.10", "0.10", "0.20", 20, "starter")
        assert float(cost_log.total()) == pytest.approx(0.35)

    def test_reset(self, cost_log: CostLog) -> None:
        cost_log.record("ep1", "0.10", "0.00", "0.10", 0, "starter")
        removed = cost_log.reset()
        assert removed == 1
        assert cost_log.entries() == []


# ---------------------------------------------------------------------------
# TaskStore — task lifecycle persistence
# ---------------------------------------------------------------------------


@pytest.fixture
def task_store(tmp_path: Path) -> TaskStore:
    return TaskStore(db_path=tmp_path / "tasks.db")


class TestTaskStore:
    def test_save_and_get(self, task_store: TaskStore) -> None:
        task_store.save("task-1", "discogen")
        task = task_store.get("task-1")
        assert task is not None
        assert task["status"] == "in_progress"

    def test_update_status(self, task_store: TaskStore) -> None:
        task_store.save("task-2", "discogen")
        task_store.update("task-2", "completed")
        task = task_store.get("task-2")
        assert task is not None
        assert task["status"] == "completed"

    def test_list_filtered(self, task_store: TaskStore) -> None:
        task_store.save("t1", "discogen")
        task_store.save("t2", "discogen")
        task_store.update("t2", "completed")
        in_prog = task_store.list(status="in_progress")
        assert len(in_prog) == 1
        assert in_prog[0]["task_id"] == "t1"

    def test_get_missing_returns_none(self, task_store: TaskStore) -> None:
        assert task_store.get("nope") is None


# ---------------------------------------------------------------------------
# CacheManager facade — backwards compat: old API still works
# ---------------------------------------------------------------------------


@pytest.fixture
def cache(tmp_path: Path) -> CacheManager:
    return CacheManager(db_path=tmp_path / "cache.db")


class TestCacheManagerFacade:
    """CacheManager wraps DataCache + CostLog + TaskStore behind the old API."""

    def test_has_data_cache_attr(self, cache: CacheManager) -> None:
        assert hasattr(cache, "data_cache")
        assert isinstance(cache.data_cache, DataCache)

    def test_has_cost_log_attr(self, cache: CacheManager) -> None:
        assert hasattr(cache, "cost_log")
        assert isinstance(cache.cost_log, CostLog)

    def test_has_task_store_attr(self, cache: CacheManager) -> None:
        assert hasattr(cache, "task_store")
        assert isinstance(cache.task_store, TaskStore)

    def test_get_delegates_to_data_cache(self, cache: CacheManager) -> None:
        cache.set("k", "v", "cat")
        assert cache.get("k", ttl=3600) == "v"

    def test_record_cost_delegates_to_cost_log(self, cache: CacheManager) -> None:
        cache.record_cost("ep", "0.10", "0.05", "0.15", 10, "starter")
        assert len(cache.get_session_costs()) == 1

    def test_save_task_delegates_to_task_store(self, cache: CacheManager) -> None:
        cache.save_task("t-1", "discogen")
        assert cache.get_task("t-1") is not None
