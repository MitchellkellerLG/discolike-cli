"""Tests for async task Pydantic models — TaskSubmitResponse and TaskStatusResponse."""

from __future__ import annotations

import pytest

from discolike.types import TaskStatusResponse, TaskSubmitResponse


class TestTaskSubmitResponse:
    def test_basic_creation(self) -> None:
        r = TaskSubmitResponse(task_id="abc", status="in_progress")
        assert r.task_id == "abc"
        assert r.status == "in_progress"

    def test_default_status(self) -> None:
        r = TaskSubmitResponse(task_id="xyz")
        assert r.status == "in_progress"

    def test_extra_fields_allowed(self) -> None:
        r = TaskSubmitResponse(task_id="abc", status="in_progress", extra_field="val")
        assert r.task_id == "abc"

    def test_extra_fields_do_not_raise(self) -> None:
        # Should not raise even with many extra fields
        r = TaskSubmitResponse(
            task_id="abc",
            status="in_progress",
            foo="bar",
            baz=123,
        )
        assert r.task_id == "abc"


class TestTaskStatusResponse:
    def test_basic_creation(self) -> None:
        r = TaskStatusResponse(status="completed", results=[{"domain": "x.com"}])
        assert r.status == "completed"
        assert r.results == [{"domain": "x.com"}]

    def test_progress_field(self) -> None:
        r = TaskStatusResponse(status="in_progress", progress=50)
        assert r.progress == 50

    def test_error_field(self) -> None:
        r = TaskStatusResponse(status="failed", error="server error")
        assert r.error == "server error"

    def test_optional_task_id(self) -> None:
        r = TaskStatusResponse(status="pending")
        assert r.task_id is None

    def test_task_id_present(self) -> None:
        r = TaskStatusResponse(task_id="t-123", status="completed")
        assert r.task_id == "t-123"

    def test_estimated_cost_field(self) -> None:
        r = TaskStatusResponse(status="completed", estimated_cost="$0.05")
        assert r.estimated_cost == "$0.05"

    def test_none_defaults(self) -> None:
        r = TaskStatusResponse(status="pending")
        assert r.task_id is None
        assert r.progress is None
        assert r.results is None
        assert r.error is None
        assert r.estimated_cost is None

    def test_extra_fields_allowed(self) -> None:
        r = TaskStatusResponse(status="completed", unknown_future_field="value")
        assert r.status == "completed"


class TestImports:
    def test_task_submit_response_importable(self) -> None:
        from discolike.types import TaskSubmitResponse  # noqa: F401

    def test_task_status_response_importable(self) -> None:
        from discolike.types import TaskStatusResponse  # noqa: F401
