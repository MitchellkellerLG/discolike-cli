"""SQLite-backed local cache with TTL support.

Three focused classes, one thin facade:
- DataCache  — TTL key/value store (cache table)
- CostLog    — append-only cost ledger (costs table)
- TaskStore  — async task lifecycle (tasks table)
- CacheManager — facade over all three, preserving the old public API
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from discolike.config import get_config_dir
from discolike.constants import CACHE_DB


# ---------------------------------------------------------------------------
# DataCache
# ---------------------------------------------------------------------------


class DataCache:
    """TTL-based key/value cache backed by SQLite."""

    def __init__(self, db_path: Path, conn: sqlite3.Connection | None = None) -> None:
        self._db_path = db_path
        self._owns_conn = conn is None
        self._conn = conn if conn is not None else sqlite3.connect(str(db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def get(self, key: str, ttl: int) -> str | None:
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
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, category, created_at) VALUES (?, ?, ?, ?)",
            (key, value, category, time.time()),
        )
        self._conn.commit()

    def clear(self, category: str | None = None) -> int:
        if category:
            cursor = self._conn.execute("DELETE FROM cache WHERE category = ?", (category,))
        else:
            cursor = self._conn.execute("DELETE FROM cache")
        self._conn.commit()
        return cursor.rowcount

    def stats(self) -> dict[str, Any]:
        rows = self._conn.execute(
            "SELECT category, COUNT(*) as count FROM cache GROUP BY category"
        ).fetchall()
        total = sum(r[1] for r in rows)
        return {
            "total_entries": total,
            "by_category": {r[0]: r[1] for r in rows},
            "db_path": str(self._db_path),
        }

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()


# ---------------------------------------------------------------------------
# CostLog
# ---------------------------------------------------------------------------


class CostLog:
    """Append-only cost ledger backed by SQLite."""

    def __init__(self, db_path: Path, conn: sqlite3.Connection | None = None) -> None:
        self._owns_conn = conn is None
        self._conn = conn if conn is not None else sqlite3.connect(str(db_path))
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

    def record(
        self,
        endpoint: str,
        query_fee: str,
        record_fee: str,
        total: str,
        records_returned: int,
        plan: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO costs "
            "(endpoint, query_fee, record_fee, total, records_returned, plan, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (endpoint, query_fee, record_fee, total, records_returned, plan, time.time()),
        )
        self._conn.commit()

    def entries(self) -> list[dict[str, Any]]:
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

    def total(self) -> str:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(CAST(total AS REAL)), 0) FROM costs"
        ).fetchone()
        return str(row[0]) if row else "0"

    def reset(self) -> int:
        cursor = self._conn.execute("DELETE FROM costs")
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()


# ---------------------------------------------------------------------------
# TaskStore
# ---------------------------------------------------------------------------


class TaskStore:
    """Async task lifecycle persistence backed by SQLite."""

    def __init__(self, db_path: Path, conn: sqlite3.Connection | None = None) -> None:
        self._owns_conn = conn is None
        self._conn = conn if conn is not None else sqlite3.connect(str(db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                status TEXT NOT NULL,
                submitted_at REAL NOT NULL,
                last_polled_at REAL,
                params_json TEXT,
                error_message TEXT
            )
        """)
        self._conn.commit()

    def save(self, task_id: str, endpoint: str, params_json: str | None = None) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tasks "
            "(task_id, endpoint, status, submitted_at, params_json) VALUES (?, ?, ?, ?, ?)",
            (task_id, endpoint, "in_progress", time.time(), params_json),
        )
        self._conn.commit()

    def update(self, task_id: str, status: str, error_message: str | None = None) -> None:
        self._conn.execute(
            "UPDATE tasks SET status = ?, last_polled_at = ?, error_message = ? WHERE task_id = ?",
            (status, time.time(), error_message, task_id),
        )
        self._conn.commit()

    def get(self, task_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT task_id, endpoint, status, submitted_at, last_polled_at, params_json, error_message "
            "FROM tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "task_id": row[0],
            "endpoint": row[1],
            "status": row[2],
            "submitted_at": row[3],
            "last_polled_at": row[4],
            "params_json": row[5],
            "error_message": row[6],
        }

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self._conn.execute(
                "SELECT task_id, endpoint, status, submitted_at, last_polled_at, params_json, error_message "
                "FROM tasks WHERE status = ? ORDER BY submitted_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT task_id, endpoint, status, submitted_at, last_polled_at, params_json, error_message "
                "FROM tasks ORDER BY submitted_at DESC"
            ).fetchall()
        return [
            {
                "task_id": r[0],
                "endpoint": r[1],
                "status": r[2],
                "submitted_at": r[3],
                "last_polled_at": r[4],
                "params_json": r[5],
                "error_message": r[6],
            }
            for r in rows
        ]

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()


# ---------------------------------------------------------------------------
# CacheManager — thin facade, preserves old public API
# ---------------------------------------------------------------------------


class CacheManager:
    """SQLite cache at ~/.discolike/cache.db with TTL-based expiry.

    Delegates to three focused components:
    - data_cache  (DataCache)   — TTL key/value
    - cost_log    (CostLog)     — cost ledger
    - task_store  (TaskStore)   — task state
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = get_config_dir() / CACHE_DB
        self._db_path = db_path
        # Single shared connection — avoids "database is locked" on concurrent ops.
        self._conn = sqlite3.connect(str(db_path))
        self.data_cache = DataCache(db_path, conn=self._conn)
        self.cost_log = CostLog(db_path, conn=self._conn)
        self.task_store = TaskStore(db_path, conn=self._conn)

    # --- DataCache facade ---

    def get(self, key: str, ttl: int) -> str | None:
        return self.data_cache.get(key, ttl)

    def set(self, key: str, value: str, category: str) -> None:
        self.data_cache.set(key, value, category)

    def clear(self, category: str | None = None) -> int:
        return self.data_cache.clear(category)

    def stats(self) -> dict[str, Any]:
        return self.data_cache.stats()

    # --- CostLog facade ---

    def record_cost(
        self,
        endpoint: str,
        query_fee: str,
        record_fee: str,
        total: str,
        records_returned: int,
        plan: str,
    ) -> None:
        self.cost_log.record(endpoint, query_fee, record_fee, total, records_returned, plan)

    def get_session_costs(self) -> list[dict[str, Any]]:
        return self.cost_log.entries()

    def get_session_total(self) -> str:
        return self.cost_log.total()

    def reset_costs(self) -> int:
        return self.cost_log.reset()

    # --- TaskStore facade ---

    def save_task(self, task_id: str, endpoint: str, params_json: str | None = None) -> None:
        self.task_store.save(task_id, endpoint, params_json)

    def update_task_status(
        self, task_id: str, status: str, error_message: str | None = None
    ) -> None:
        self.task_store.update(task_id, status, error_message)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self.task_store.get(task_id)

    def list_tasks(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        return self.task_store.list(status_filter)

    def close(self) -> None:
        self._conn.close()
