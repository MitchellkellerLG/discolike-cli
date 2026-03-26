"""SQLite-backed local cache with TTL support."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from discolike.config import get_config_dir
from discolike.constants import CACHE_DB


class CacheManager:
    """SQLite cache at ~/.discolike/cache.db with TTL-based expiry."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = get_config_dir() / CACHE_DB
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                query_fee TEXT NOT NULL,
                record_fee TEXT NOT NULL,
                total TEXT NOT NULL,
                records_returned INTEGER NOT NULL,
                plan TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def get(self, key: str, ttl: int) -> str | None:
        """Get cached value if not expired. Returns None if missing or expired."""
        row = self._conn.execute(
            "SELECT value, created_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, created_at = row
        if time.time() - created_at > ttl:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return str(value)

    def set(self, key: str, value: str, category: str) -> None:
        """Set a cached value."""
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, category, created_at) VALUES (?, ?, ?, ?)",
            (key, value, category, time.time()),
        )
        self._conn.commit()

    def clear(self, category: str | None = None) -> int:
        """Clear cache entries. If category given, only that category."""
        if category:
            cursor = self._conn.execute(
                "DELETE FROM cache WHERE category = ?", (category,)
            )
        else:
            cursor = self._conn.execute("DELETE FROM cache")
        self._conn.commit()
        return cursor.rowcount

    def stats(self) -> dict[str, Any]:
        """Return cache statistics by category."""
        rows = self._conn.execute(
            "SELECT category, COUNT(*) as count FROM cache GROUP BY category"
        ).fetchall()
        total = sum(r[1] for r in rows)
        return {
            "total_entries": total,
            "by_category": {r[0]: r[1] for r in rows},
            "db_path": str(self._db_path),
        }

    # --- Cost persistence ---

    def record_cost(
        self,
        endpoint: str,
        query_fee: str,
        record_fee: str,
        total: str,
        records_returned: int,
        plan: str,
    ) -> None:
        """Persist a cost entry."""
        self._conn.execute(
            "INSERT INTO costs "
            "(endpoint, query_fee, record_fee, total, records_returned, plan, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (endpoint, query_fee, record_fee, total, records_returned, plan, time.time()),
        )
        self._conn.commit()

    def get_session_costs(self) -> list[dict[str, Any]]:
        """Get all persisted cost entries."""
        rows = self._conn.execute(
            "SELECT endpoint, query_fee, record_fee, total, records_returned, plan, created_at "
            "FROM costs ORDER BY id"
        ).fetchall()
        return [
            {
                "endpoint": r[0],
                "query_fee": r[1],
                "record_fee": r[2],
                "total": r[3],
                "records_returned": r[4],
                "plan": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]

    def get_session_total(self) -> str:
        """Get sum of all session costs."""
        row = self._conn.execute(
            "SELECT COALESCE(SUM(CAST(total AS REAL)), 0) FROM costs"
        ).fetchone()
        return str(row[0]) if row else "0"

    def reset_costs(self) -> int:
        """Clear all session cost entries."""
        cursor = self._conn.execute("DELETE FROM costs")
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
