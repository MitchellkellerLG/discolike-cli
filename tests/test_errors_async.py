"""Tests for async task error classes — TaskError and TaskTimeoutError."""

from __future__ import annotations

import pytest

from discolike.errors import DiscoLikeError, TaskError, TaskTimeoutError


class TestTaskError:
    def test_basic_creation(self) -> None:
        e = TaskError("task failed")
        assert str(e) == "task failed"

    def test_exit_code(self) -> None:
        e = TaskError("msg")
        assert e.exit_code == 1

    def test_default_suggestion_contains_status_command(self) -> None:
        e = TaskError("msg")
        assert "discolike tasks status" in e.suggestion

    def test_custom_suggestion_overrides_default(self) -> None:
        e = TaskError("msg", suggestion="custom hint")
        assert e.suggestion == "custom hint"

    def test_is_subclass_of_discolike_error(self) -> None:
        e = TaskError("msg")
        assert isinstance(e, DiscoLikeError)

    def test_except_discolike_error_catches_task_error(self) -> None:
        with pytest.raises(DiscoLikeError):
            raise TaskError("msg")


class TestTaskTimeoutError:
    def test_basic_creation(self) -> None:
        e = TaskTimeoutError("timed out")
        assert str(e) == "timed out"

    def test_exit_code(self) -> None:
        e = TaskTimeoutError("msg")
        assert e.exit_code == 1

    def test_is_subclass_of_task_error(self) -> None:
        e = TaskTimeoutError("msg")
        assert isinstance(e, TaskError)

    def test_is_subclass_of_discolike_error(self) -> None:
        e = TaskTimeoutError("msg")
        assert isinstance(e, DiscoLikeError)

    def test_except_task_error_catches_timeout(self) -> None:
        """except TaskError should also catch TaskTimeoutError."""
        with pytest.raises(TaskError):
            raise TaskTimeoutError("timed out")

    def test_custom_suggestion(self) -> None:
        e = TaskTimeoutError("timed out", suggestion="custom")
        assert e.suggestion == "custom"

    def test_default_suggestion_inherits_from_task_error(self) -> None:
        e = TaskTimeoutError("msg")
        assert "discolike tasks status" in e.suggestion


class TestImports:
    def test_task_error_importable(self) -> None:
        from discolike.errors import TaskError  # noqa: F401

    def test_task_timeout_error_importable(self) -> None:
        from discolike.errors import TaskTimeoutError  # noqa: F401
