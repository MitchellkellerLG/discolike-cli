---
phase: 01-async-infrastructure
plan: "01"
subsystem: core-infrastructure
tags: [pydantic, sqlite, http-client, async-tasks, tdd]
dependency_graph:
  requires: []
  provides: [TaskSubmitResponse, TaskStatusResponse, TaskError, TaskTimeoutError, CacheManager.tasks, DiscoLikeClient.async-methods]
  affects: [plan-02-async-task-manager]
tech_stack:
  added: []
  patterns: [INSERT-OR-REPLACE for task upsert, shared-status-endpoint for all async tasks]
key_files:
  created:
    - tests/test_types_async.py
    - tests/test_errors_async.py
  modified:
    - src/discolike/types.py
    - src/discolike/errors.py
    - src/discolike/cache.py
    - src/discolike/client.py
    - tests/test_cache.py
    - tests/test_client.py
decisions:
  - All three async endpoints (DiscoGen, ValidateICP, Segment) poll via shared /discogen/status/{task_id}
  - task_status and task_cancel make HTTP even in dry_run mode (they need real task_ids)
  - INSERT OR REPLACE used for save_task to handle idempotent re-submission
metrics:
  duration_seconds: 186
  completed_date: "2026-04-08"
  tasks_completed: 3
  files_modified: 6
---

# Phase 01 Plan 01: Async Task Foundation Summary

**One-liner:** Pydantic task models, SQLite tasks table with CRUD, DELETE support in httpx client, and 5 async client methods — tested foundation for AsyncTaskManager.

## What Was Built

Three TDD cycles producing the complete async infrastructure layer:

**Task 1 — Types and errors** (`src/discolike/types.py`, `src/discolike/errors.py`):
- `TaskSubmitResponse` — Pydantic model for task submission responses with `extra="allow"` for API evolution
- `TaskStatusResponse` — polling model with optional task_id, progress, results, error, estimated_cost fields
- `TaskError(DiscoLikeError)` — exit_code=1, default suggestion pointing to `discolike tasks status`
- `TaskTimeoutError(TaskError)` — subclasses TaskError so `except TaskError` catches both

**Task 2 — CacheManager tasks table** (`src/discolike/cache.py`, `tests/test_cache.py`):
- `tasks` table added to `_init_tables()` alongside existing cache and costs tables
- Schema: task_id PK, endpoint, status, submitted_at REAL, last_polled_at REAL, params_json TEXT, error_message TEXT
- `save_task(task_id, endpoint, params_json)` — INSERT OR REPLACE with status="in_progress"
- `update_task_status(task_id, status, error_message)` — sets status + last_polled_at timestamp
- `get_task(task_id)` — returns dict or None if not found
- `list_tasks(status_filter)` — returns all tasks, optionally filtered

**Task 3 — Client async methods and DELETE** (`src/discolike/client.py`, `tests/test_client.py`):
- DELETE branch added to `_request()` before the POST fallback
- `discogen_submit(params)` — thin POST to `/discogen/process`
- `validate_icp_submit(params)` — thin POST to `/validate/icp`
- `segment_submit(params)` — thin POST to `/segment`
- `task_status(task_id)` — GET `/discogen/status/{task_id}` (shared endpoint for all three async ops)
- `task_cancel(task_id)` — DELETE `/discogen/cancel/{task_id}`

## Test Coverage

| File | Tests | Result |
|------|-------|--------|
| tests/test_types_async.py | 14 | PASS |
| tests/test_errors_async.py | 15 | PASS |
| tests/test_cache.py (new: TestTasksPersistence) | 13 new / 31 total | PASS |
| tests/test_client.py (new: TestAsyncSubmit, TestTaskStatus, TestTaskCancel) | 11 new / 36 total | PASS |
| **Total** | **96** | **100% green** |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all methods are fully wired. Dry-run returns stub dict only for submit methods (by design per plan spec), not for status/cancel.

## Commits

| Hash | Message |
|------|---------|
| 0a74219 | feat(01-01): add TaskSubmitResponse, TaskStatusResponse, TaskError, TaskTimeoutError |
| c76e37a | feat(01-01): add tasks table and CRUD methods to CacheManager |
| 54887f8 | feat(01-01): add DELETE support and 5 async methods to DiscoLikeClient |

## Self-Check: PASSED
