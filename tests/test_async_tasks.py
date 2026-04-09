"""Tests for AsyncTaskManager -- poll/cancel/resume/list_tasks lifecycle."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from discolike.async_tasks import AsyncTaskManager
from discolike.cache import CacheManager
from discolike.errors import TaskError, TaskTimeoutError


@pytest.fixture
def cache(tmp_path: Path) -> CacheManager:
    """Real CacheManager using tmp_path SQLite."""
    return CacheManager(db_path=tmp_path / "test_tasks.db")


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock DiscoLikeClient."""
    return MagicMock()


@pytest.fixture
def manager(mock_client: MagicMock, cache: CacheManager) -> AsyncTaskManager:
    """AsyncTaskManager with mock client and real cache."""
    return AsyncTaskManager(mock_client, cache)


class TestPollLifecycle:
    """Test the core poll() lifecycle transitions."""

    def test_complete_on_first_check(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() returns result immediately if task completes on first check."""
        task_id = "t-001"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.return_value = {
            "task_id": task_id,
            "status": "completed",
            "results": [{"domain": "acme.com"}],
        }

        with patch("time.sleep"):
            result = manager.poll(task_id)

        assert result["status"] == "completed"
        assert mock_client.task_status.call_count == 1
        cached = cache.get_task(task_id)
        assert cached is not None
        assert cached["status"] == "completed"

    def test_complete_status_alias(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() treats 'complete' (no d) as terminal success."""
        task_id = "t-002"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.return_value = {"task_id": task_id, "status": "complete"}

        with patch("time.sleep"):
            result = manager.poll(task_id)

        assert result["status"] == "complete"
        cached = cache.get_task(task_id)
        assert cached is not None
        assert cached["status"] == "completed"

    def test_complete_on_third_check(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() returns result after 3 status checks, updates cache to completed."""
        task_id = "t-003"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.side_effect = [
            {"task_id": task_id, "status": "in_progress"},
            {"task_id": task_id, "status": "in_progress"},
            {"task_id": task_id, "status": "completed", "results": []},
        ]

        with patch("time.sleep"):
            result = manager.poll(task_id)

        assert result["status"] == "completed"
        assert mock_client.task_status.call_count == 3
        cached = cache.get_task(task_id)
        assert cached is not None
        assert cached["status"] == "completed"

    def test_failed_task_raises_task_error(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() raises TaskError with error message when task status is 'failed'."""
        task_id = "t-004"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.return_value = {
            "task_id": task_id,
            "status": "failed",
            "error": "LLM quota exceeded",
        }

        with patch("time.sleep"), pytest.raises(TaskError, match="LLM quota exceeded"):
            manager.poll(task_id)

    def test_failed_task_updates_cache(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() updates cache to 'failed' with error_message on failure."""
        task_id = "t-005"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.return_value = {
            "task_id": task_id,
            "status": "failed",
            "error": "API error",
        }

        with patch("time.sleep"), pytest.raises(TaskError):
            manager.poll(task_id)

        cached = cache.get_task(task_id)
        assert cached is not None
        assert cached["status"] == "failed"
        assert cached["error_message"] == "API error"

    def test_unknown_status_keeps_polling(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() continues polling for unrecognized intermediate status values."""
        task_id = "t-006"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.side_effect = [
            {"status": "queued"},
            {"status": "processing"},
            {"status": "completed", "results": []},
        ]

        with patch("time.sleep"):
            result = manager.poll(task_id)

        assert result["status"] == "completed"
        assert mock_client.task_status.call_count == 3


class TestPollBackoff:
    """Test the linear-to-capped backoff interval pattern."""

    def test_backoff_follows_3_6_9_12_15_15_pattern(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """Intervals follow 3, 6, 9, 12, 15, 15, 15... capped at 15s."""
        task_id = "t-backoff"
        cache.save_task(task_id, "discogen")

        # Return in_progress 7 times, then complete
        responses = [{"status": "in_progress"}] * 7 + [{"status": "completed"}]
        mock_client.task_status.side_effect = responses

        sleep_calls: list[float] = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            manager.poll(task_id)

        assert sleep_calls == [3.0, 6.0, 9.0, 12.0, 15.0, 15.0, 15.0]

    def test_backoff_custom_params(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """Custom initial_interval, interval_step, max_interval are respected."""
        task_id = "t-custom"
        cache.save_task(task_id, "discogen")

        responses = [{"status": "in_progress"}] * 4 + [{"status": "completed"}]
        mock_client.task_status.side_effect = responses

        sleep_calls: list[float] = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            manager.poll(
                task_id,
                initial_interval=10.0,
                interval_step=10.0,
                max_interval=30.0,
            )

        assert sleep_calls == [10.0, 20.0, 30.0, 30.0]


class TestPollTimeout:
    """Test timeout behavior via wall clock elapsed time."""

    def test_timeout_raises_task_timeout_error(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() raises TaskTimeoutError when elapsed >= max_elapsed."""
        task_id = "t-timeout"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.return_value = {"status": "in_progress"}

        # Simulate elapsed time passing max_elapsed on second call
        time_values = [0.0, 0.0, 301.0]  # start, first check, second check exceeds 300s
        call_count = [0]

        def fake_time() -> float:
            val = time_values[min(call_count[0], len(time_values) - 1)]
            call_count[0] += 1
            return val

        with (
            patch("time.sleep"),
            patch("time.time", side_effect=fake_time),
            pytest.raises(TaskTimeoutError),
        ):
            manager.poll(task_id, max_elapsed=300.0)

    def test_timeout_uses_wall_clock_not_interval_sum(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """Elapsed is computed as time.time() - start_time (Pitfall 4)."""
        task_id = "t-wallclock"
        cache.save_task(task_id, "discogen")

        # Simulate slow API calls: each status call takes 60s of real time
        # With 2 calls: 120s elapsed but interval sum would only be 3+6=9s
        time_values = iter([0.0, 60.0, 120.0, 180.0, 240.0, 300.0, 360.0])

        mock_client.task_status.return_value = {"status": "in_progress"}

        with (
            patch("time.sleep"),
            patch("time.time", side_effect=lambda: next(time_values)),
            pytest.raises(TaskTimeoutError),
        ):
            manager.poll(task_id, max_elapsed=300.0)


class TestPollCallback:
    """Test on_status callback invocation."""

    def test_callback_called_with_correct_args(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """on_status receives (status_string, attempt_number, elapsed_seconds)."""
        task_id = "t-callback"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.side_effect = [
            {"status": "in_progress"},
            {"status": "completed"},
        ]

        received: list[tuple[str, int, float]] = []

        def capture(status: str, attempt: int, elapsed: float) -> None:
            received.append((status, attempt, elapsed))

        with patch("time.sleep"), patch("time.time", return_value=0.0):
            manager.poll(task_id, on_status=capture)

        assert len(received) == 2
        assert received[0] == ("in_progress", 1, 0.0)
        assert received[1] == ("completed", 2, 0.0)

    def test_no_callback_does_not_raise(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() works fine with on_status=None (default)."""
        task_id = "t-no-cb"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.return_value = {"status": "completed"}

        with patch("time.sleep"):
            result = manager.poll(task_id, on_status=None)

        assert result["status"] == "completed"


class TestCtrlCInterrupt:
    """Test KeyboardInterrupt handling: cache write BEFORE stderr print."""

    def test_keyboard_interrupt_sets_interrupted_status(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() sets cache status to 'interrupted' on Ctrl+C."""
        task_id = "t-ctrl-c"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.side_effect = KeyboardInterrupt

        with patch("time.sleep"), pytest.raises(SystemExit) as exc_info:
            manager.poll(task_id)

        assert exc_info.value.code == 0
        cached = cache.get_task(task_id)
        assert cached is not None
        assert cached["status"] == "interrupted"

    def test_keyboard_interrupt_prints_resume_message_to_stderr(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """poll() prints task_id and resume command to stderr on Ctrl+C."""
        task_id = "t-ctrl-c-msg"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.side_effect = KeyboardInterrupt

        with patch("time.sleep"), pytest.raises(SystemExit):
            manager.poll(task_id)

        captured = capsys.readouterr()
        assert f"Task {task_id} still running on server." in captured.err
        assert f"discolike tasks resume {task_id}" in captured.err

    def test_keyboard_interrupt_raises_system_exit_0(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """poll() raises SystemExit(0) on Ctrl+C (clean exit, not error)."""
        task_id = "t-exit-0"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.side_effect = KeyboardInterrupt

        with patch("time.sleep"), pytest.raises(SystemExit) as exc_info:
            manager.poll(task_id)

        assert exc_info.value.code == 0


class TestInterruptOrder:
    """Verify cache write happens BEFORE stderr print (D-09 ordering)."""

    def test_cache_written_before_stderr_print(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """update_task_status('interrupted') must be called before print to stderr."""
        task_id = "t-order"
        cache.save_task(task_id, "discogen")
        mock_client.task_status.side_effect = KeyboardInterrupt

        call_order: list[str] = []

        original_update = cache.update_task_status

        def tracked_update(tid: str, status: str, error: str | None = None) -> None:
            call_order.append(f"cache.update_task_status:{status}")
            original_update(tid, status, error)

        import builtins
        original_print = builtins.print

        def tracked_print(*args: object, **kwargs: object) -> None:
            import sys as _sys
            if kwargs.get("file") is _sys.stderr:
                call_order.append("stderr.print")
            original_print(*args, **kwargs)

        cache.update_task_status = tracked_update  # type: ignore[method-assign]

        with (
            patch("time.sleep"),
            patch("builtins.print", side_effect=tracked_print),
            pytest.raises(SystemExit),
        ):
            manager.poll(task_id)

        # Cache write must come before stderr print
        interrupted_idx = next(
            i for i, s in enumerate(call_order) if "interrupted" in s
        )
        stderr_idx = next(i for i, s in enumerate(call_order) if s == "stderr.print")
        assert interrupted_idx < stderr_idx, (
            f"Expected cache write before stderr print, got order: {call_order}"
        )


class TestCancel:
    """Test cancel() -- calls client.task_cancel and updates cache."""

    def test_cancel_calls_client_and_updates_cache(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """cancel() calls task_cancel and sets cache status to 'cancelled'."""
        task_id = "t-cancel"
        cache.save_task(task_id, "discogen")
        mock_client.task_cancel.return_value = {"status": "cancelled", "task_id": task_id}

        result = manager.cancel(task_id)

        mock_client.task_cancel.assert_called_once_with(task_id)
        assert result["status"] == "cancelled"

        cached = cache.get_task(task_id)
        assert cached is not None
        assert cached["status"] == "cancelled"

    def test_cancel_returns_api_response(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """cancel() returns the raw API response dict."""
        task_id = "t-cancel-resp"
        cache.save_task(task_id, "discogen")
        expected = {"status": "cancelled", "task_id": task_id, "message": "Task cancelled"}
        mock_client.task_cancel.return_value = expected

        result = manager.cancel(task_id)

        assert result == expected


class TestResume:
    """Test resume() -- re-polls a previously interrupted task."""

    def test_resume_repolls_existing_task(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """resume() retrieves task from cache and calls poll()."""
        task_id = "t-resume"
        cache.save_task(task_id, "discogen")
        cache.update_task_status(task_id, "interrupted")

        mock_client.task_status.return_value = {"status": "completed", "results": []}

        with patch("time.sleep"):
            result = manager.resume(task_id)

        assert result["status"] == "completed"
        mock_client.task_status.assert_called_once_with(task_id)

    def test_resume_sets_status_to_in_progress(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """resume() resets cache status to 'in_progress' before re-polling."""
        task_id = "t-resume-status"
        cache.save_task(task_id, "discogen")
        cache.update_task_status(task_id, "interrupted")

        statuses_seen: list[str] = []

        original_update = cache.update_task_status

        def track_update(tid: str, status: str, error: str | None = None) -> None:
            statuses_seen.append(status)
            original_update(tid, status, error)

        cache.update_task_status = track_update  # type: ignore[method-assign]
        mock_client.task_status.return_value = {"status": "completed"}

        with patch("time.sleep"):
            manager.resume(task_id)

        assert "in_progress" in statuses_seen

    def test_resume_unknown_task_raises_task_error(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """resume() raises TaskError for task_id not in local cache."""
        with pytest.raises(TaskError, match="not found in local task history"):
            manager.resume("nonexistent-task-id")

    def test_resume_passes_poll_kwargs(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """resume() passes **kwargs through to poll()."""
        task_id = "t-resume-kwargs"
        cache.save_task(task_id, "discogen")
        cache.update_task_status(task_id, "interrupted")

        responses = [{"status": "in_progress"}] * 2 + [{"status": "completed"}]
        mock_client.task_status.side_effect = responses

        sleep_calls: list[float] = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            manager.resume(task_id, initial_interval=30.0, interval_step=0.0, max_interval=30.0)

        # All sleeps should be 30.0
        assert all(s == 30.0 for s in sleep_calls)


class TestListTasks:
    """Test list_tasks() -- delegates to cache.list_tasks."""

    def test_list_tasks_delegates_to_cache(
        self, manager: AsyncTaskManager, cache: CacheManager
    ) -> None:
        """list_tasks() returns tasks from cache."""
        cache.save_task("t-list-1", "discogen")
        cache.save_task("t-list-2", "validate/icp")

        tasks = manager.list_tasks()

        assert len(tasks) == 2
        task_ids = {t["task_id"] for t in tasks}
        assert task_ids == {"t-list-1", "t-list-2"}

    def test_list_tasks_with_status_filter(
        self, manager: AsyncTaskManager, cache: CacheManager
    ) -> None:
        """list_tasks(status_filter=...) passes filter through to cache."""
        cache.save_task("t-list-a", "discogen")
        cache.save_task("t-list-b", "discogen")
        cache.update_task_status("t-list-b", "completed")

        in_progress = manager.list_tasks(status_filter="in_progress")
        completed = manager.list_tasks(status_filter="completed")

        assert len(in_progress) == 1
        assert in_progress[0]["task_id"] == "t-list-a"
        assert len(completed) == 1
        assert completed[0]["task_id"] == "t-list-b"

    def test_list_tasks_empty_cache(
        self, manager: AsyncTaskManager
    ) -> None:
        """list_tasks() returns empty list when no tasks exist."""
        result = manager.list_tasks()
        assert result == []


class TestSubmitPersistPoll:
    """Integration test: the full submit -> persist -> poll pattern (D-03).

    This tests the intended call sequence that Phase 2+ commands will use:
    1. client.discogen_submit(params) -> response with task_id
    2. cache.save_task(task_id, endpoint, params_json) -- BEFORE poll
    3. task_manager.poll(task_id) -> result
    """

    def test_submit_persist_poll_complete_cycle(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """Full submit -> save_task -> poll cycle completes correctly."""
        params = {"domains": ["acme.com"], "prompt": "Describe their product"}

        # Step 1: submit
        mock_client.discogen_submit.return_value = {
            "task_id": "t-integration-001",
            "status": "in_progress",
        }
        submit_resp = mock_client.discogen_submit(params)
        task_id = submit_resp["task_id"]

        # Step 2: persist BEFORE poll (D-03)
        import json as _json
        cache.save_task(task_id, "discogen/process", _json.dumps(params))

        # Verify task is in cache before poll starts
        pre_poll_task = cache.get_task(task_id)
        assert pre_poll_task is not None
        assert pre_poll_task["status"] == "in_progress"

        # Step 3: poll
        mock_client.task_status.side_effect = [
            {"task_id": task_id, "status": "in_progress"},
            {"task_id": task_id, "status": "completed", "results": [{"summary": "B2B SaaS"}]},
        ]

        with patch("time.sleep"):
            result = manager.poll(task_id)

        assert result["status"] == "completed"

        # Verify final cache state
        final_task = cache.get_task(task_id)
        assert final_task is not None
        assert final_task["status"] == "completed"

    def test_persist_before_poll_guarantees_survivability(
        self, manager: AsyncTaskManager, mock_client: MagicMock, cache: CacheManager
    ) -> None:
        """If Ctrl+C hits during poll, task is in cache (was saved before poll)."""
        params = {"domains": ["acme.com"]}

        # Step 1: submit
        mock_client.discogen_submit.return_value = {
            "task_id": "t-survive-001",
            "status": "in_progress",
        }
        submit_resp = mock_client.discogen_submit(params)
        task_id = submit_resp["task_id"]

        # Step 2: persist before poll
        cache.save_task(task_id, "discogen/process")

        # Step 3: poll but KeyboardInterrupt hits on first status check
        mock_client.task_status.side_effect = KeyboardInterrupt

        with patch("time.sleep"), pytest.raises(SystemExit) as exc_info:
            manager.poll(task_id)

        assert exc_info.value.code == 0

        # Task must be in cache with "interrupted" status
        task_record = cache.get_task(task_id)
        assert task_record is not None, "Task must survive interrupt (was saved before poll)"
        assert task_record["status"] == "interrupted"
