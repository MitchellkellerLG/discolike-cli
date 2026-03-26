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
