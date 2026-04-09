"""Shared async task lifecycle manager for all async endpoints."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import Any

from discolike.cache import CacheManager
from discolike.client import DiscoLikeClient
from discolike.errors import TaskError, TaskTimeoutError


class AsyncTaskManager:
    """Manages poll/cancel/resume lifecycle for async API tasks.

    Composition over inheritance: takes a DiscoLikeClient and CacheManager
    as constructor arguments (D-04). Client handles HTTP, cache handles
    persistence, this class handles lifecycle.

    Note for Phase 4 (Segment): segment has 2 req/min rate limit.
    Callers can override initial_interval and max_interval to accommodate.
    """

    def __init__(self, client: DiscoLikeClient, cache: CacheManager) -> None:
        self._client = client
        self._cache = cache

    def poll(
        self,
        task_id: str,
        on_status: Callable[[str, int, float], None] | None = None,
        on_result: Callable[[dict[str, Any], int, float], None] | None = None,
        initial_interval: float = 3.0,
        interval_step: float = 3.0,
        max_interval: float = 15.0,
        max_elapsed: float = 300.0,
    ) -> dict[str, Any]:
        """Poll task_status until complete/failed/timeout.

        Args:
            task_id: The task to poll.
            on_status: Optional callback(status, attempt, elapsed) for display.
            on_result: Optional callback(result_dict, attempt, elapsed) called
                on every poll iteration with the full raw API response. Useful
                for inspecting interim_results before task completes.
            initial_interval: First sleep interval in seconds (D-11: 3.0).
            interval_step: Increment per iteration (D-11: 3.0).
            max_interval: Cap on sleep interval (D-11: 15.0).
            max_elapsed: Hard timeout in seconds (D-11: 300.0).

        Returns:
            Result dict from the API when status is completed/complete.

        Raises:
            TaskError: If task status is "failed".
            TaskTimeoutError: If max_elapsed exceeded.
            SystemExit(0): On KeyboardInterrupt (after persisting state).
        """
        start_time = time.time()  # Wall clock, not sum of intervals (Pitfall 4)
        interval = initial_interval
        attempt = 0

        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed >= max_elapsed:
                    self._cache.update_task_status(task_id, "timeout")
                    raise TaskTimeoutError(
                        f"Task {task_id} timed out after {max_elapsed:.0f}s.",
                        suggestion=f"Check task status with: discolike tasks status {task_id}",
                    )

                result = self._client.task_status(task_id)
                status = result.get("status", "unknown")
                attempt += 1

                self._cache.update_task_status(task_id, status)

                if on_status is not None:
                    on_status(status, attempt, elapsed)

                if on_result is not None:
                    on_result(result, attempt, elapsed)

                if status in ("completed", "complete"):
                    self._cache.update_task_status(task_id, "completed")
                    return result

                if status == "failed":
                    error = result.get("error", "Unknown error")
                    self._cache.update_task_status(task_id, "failed", error)
                    raise TaskError(f"Task {task_id} failed: {error}")

                time.sleep(interval)
                interval = min(interval + interval_step, max_interval)

        except KeyboardInterrupt:
            # D-09: SQLite write BEFORE stderr print
            self._cache.update_task_status(task_id, "interrupted")
            # D-10: exact message format
            print(
                f"\nTask {task_id} still running on server. "
                f"Resume with: discolike tasks resume {task_id}",
                file=sys.stderr,
            )
            raise SystemExit(0)

    def cancel(self, task_id: str) -> dict[str, Any]:
        """Cancel a running task via API and update local state."""
        result = self._client.task_cancel(task_id)
        self._cache.update_task_status(task_id, "cancelled")
        return result

    def resume(self, task_id: str, **poll_kwargs: Any) -> dict[str, Any]:
        """Resume polling a previously interrupted task.

        Args:
            task_id: The task to resume.
            **poll_kwargs: Passed through to poll().

        Raises:
            TaskError: If task_id not found in local cache.
        """
        task = self._cache.get_task(task_id)
        if task is None:
            raise TaskError(
                f"Task {task_id} not found in local task history.",
                suggestion="Use 'discolike tasks list' to see known tasks.",
            )
        self._cache.update_task_status(task_id, "in_progress")
        return self.poll(task_id, **poll_kwargs)

    def list_tasks(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        """List tasks from local cache, optionally filtered by status."""
        return self._cache.list_tasks(status_filter=status_filter)
