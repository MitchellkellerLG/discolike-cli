# Phase 1: Async Infrastructure - Research

**Researched:** 2026-04-08
**Domain:** Python CLI async task lifecycle — SQLite persistence, polling backoff, Ctrl+C handling, Rich progress
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Task Persistence**
- D-01: Tasks table lives in the same `~/.discolike/cache.db` used by CacheManager — no second database file. CacheManager already manages SQLite connections and table creation.
- D-02: Tasks table schema: `task_id TEXT PRIMARY KEY, endpoint TEXT NOT NULL, status TEXT NOT NULL, submitted_at REAL NOT NULL, last_polled_at REAL, params_json TEXT, error_message TEXT`. Minimal — enough to resume/cancel, params_json stores original submission for display. No results storage (results come from API).
- D-03: Task persistence happens BEFORE first poll — `task_id` is written to SQLite immediately after the submit API call returns, before any polling begins. This is the core survivability guarantee.

**AsyncTaskManager Design**
- D-04: AsyncTaskManager is a standalone class (composition, not inheritance) that takes a `DiscoLikeClient` and a `CacheManager` as constructor arguments. Keeps `client.py` focused on HTTP, task manager handles lifecycle.
- D-05: Core methods: `submit(endpoint, params) -> task_id`, `poll(task_id, on_status=callback) -> result`, `cancel(task_id) -> bool`, `resume(task_id) -> result`, `list_tasks(status_filter) -> list`.
- D-06: `poll()` accepts an `on_status` callback that receives status string updates for Rich display. Simpler than generators, aligns with existing Rich usage patterns.

**Client Submit Methods**
- D-07: Client gains thin submit methods: `discogen_submit()`, `validate_icp_submit()`, `segment_submit()`. These call the POST endpoint and return the raw response including `task_id`. They do NOT poll — that's AsyncTaskManager's job.
- D-08: Client also gains `task_status(task_id)` and `task_cancel(task_id)` methods wrapping the status/cancel API endpoints.

**Signal Handling**
- D-09: Ctrl+C handled via `try/except KeyboardInterrupt` wrapping the poll loop — no global signal handlers, no atexit hooks. The except block prints task_id to stderr and persists "interrupted" status to SQLite.
- D-10: The message format on Ctrl+C: `"\nTask {task_id} still running on server. Resume with: discolike tasks resume {task_id}"` — printed to stderr.

**Polling Backoff**
- D-11: Linear-to-capped backoff: starts at 3s, increases by 3s each iteration (3, 6, 9, 12, 15, 15, 15...), capped at 15s. Hard timeout at 300s total elapsed.
- D-12: Progress display uses `rich.console.Console.status()` spinner with status text updates (e.g., "Polling task abc123... (attempt 4, 12s elapsed)"). Degrades gracefully when not TTY — falls back to periodic stderr lines.

### Claude's Discretion

- File organization within `src/discolike/` — whether AsyncTaskManager goes in a new `tasks.py` or `async_tasks.py`
- Internal helper method naming and decomposition
- Test file organization and fixture structure
- Whether to extend CacheManager with a task-specific method or keep task SQL in AsyncTaskManager

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Shared AsyncTaskManager handles poll/progress/cancel lifecycle for all async endpoints (DiscoGen, Validate ICP, Segment) | Composition pattern established in D-04/D-05. Polling loop pattern documented in STACK.md. No new library needed. |
| INFRA-02 | SQLite `tasks` table persists task_id before first poll — survives CLI exit, prevents orphaned jobs | CacheManager `_init_tables()` pattern directly reusable. Schema locked in D-02. Write-before-poll order locked in D-03. |
| INFRA-03 | Client gains submit/status/cancel methods for all async endpoints (`discogen_submit`, `validate_icp_submit`, `segment_submit`, `task_status`, `task_cancel`) | All five method signatures documented in ARCHITECTURE.md. `_post_json()` and `_get_with_params()` are the HTTP helpers to use. |
| INFRA-04 | Ctrl+C signal handler prints task_id to stderr and persists state before exit | `try/except KeyboardInterrupt` pattern locked in D-09. stderr message format locked in D-10. Update status to "interrupted" in SQLite before printing. |
| INFRA-05 | Polling uses linear-to-capped backoff (3s initial, 15s cap, 300s hard timeout) | Linear-to-capped arithmetic locked in D-11: `interval = min(interval + 3, 15)`. Hard timeout via `elapsed >= 300` check before sleep. |
</phase_requirements>

## Summary

This phase is pure infrastructure — no user-facing commands ship. It creates the shared plumbing that all async CLI commands (Phase 2+) will consume: `AsyncTaskManager`, the `tasks` SQLite table, five new client methods, new Pydantic types, and two new error classes.

The design decisions are fully locked in CONTEXT.md. Research confirms these decisions align with existing code patterns. The key implementation tension is the Ctrl+C path: the `except KeyboardInterrupt` block must update SQLite status BEFORE printing to stderr — if the print fails for any reason (pipe broken, etc.), the task_id is still persisted. Both operations are in-process and fast, so ordering matters more than atomicity.

The existing test infrastructure (pytest 9.0.2, respx 0.22.0, CliRunner with `mix_stderr=False`) covers all test patterns needed. The 28 pre-existing failures in `test_workflow.py` and `test_plan_gate.py` are not related to this phase — the core test infrastructure (cache, client) is green.

**Primary recommendation:** Build in dependency order — CacheManager tasks table first, then client methods, then AsyncTaskManager, then types/errors. Each layer is testable in isolation before the next layer depends on it.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib: `sqlite3` | 3.11 built-in | Tasks table persistence | Already used in CacheManager — same connection |
| Python stdlib: `time` | 3.11 built-in | `time.sleep()` for poll intervals, `time.time()` for elapsed tracking | Consistent with existing retry logic in `_request()` |
| Rich | 13.x (installed) | `console.status()` spinner during poll, fallback stderr lines | Already a dependency; `console.status()` is the existing progress pattern |
| Pydantic v2 | 2.x (installed) | `TaskSubmitResponse`, `TaskStatusResponse` models | All API response shapes use Pydantic v2 — consistency |
| httpx | 0.27+ (installed) | HTTP for task_status GET and task_cancel DELETE via existing `_request()` | No new HTTP infrastructure — same client |

### No New Dependencies
Phase 1 introduces zero new PyPI packages. All capabilities come from the existing stack and stdlib.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `time.sleep()` polling | `tenacity` / `backoff` | Wrong abstraction. `pending` is expected state, not an exception. Adds a dep for a `while` loop. |
| `try/except KeyboardInterrupt` | `signal.signal(SIGINT, handler)` | Global signal handlers have side effects across threads and test isolation. `except KeyboardInterrupt` is scoped to the poll loop — simpler and safer. |
| `atexit` hooks for task_id print | `try/except KeyboardInterrupt` | `atexit` runs on normal exit too, producing spurious messages. Locked decision D-09 explicitly excludes it. |
| Separate `tasks.db` | Same `cache.db` | Two database files adds connection management complexity. Locked decision D-01. |

## Architecture Patterns

### Recommended Project Structure
```
src/discolike/
├── async_tasks.py       # NEW — AsyncTaskManager class
├── cache.py             # MODIFIED — add tasks table to _init_tables() + task CRUD methods
├── client.py            # MODIFIED — add 5 new methods: discogen_submit, validate_icp_submit, segment_submit, task_status, task_cancel
├── types.py             # MODIFIED — add TaskSubmitResponse, TaskStatusResponse Pydantic models
├── errors.py            # MODIFIED — add TaskError, TaskTimeoutError

tests/
├── test_async_tasks.py  # NEW — AsyncTaskManager tests
├── test_cache.py        # MODIFIED — add tasks table tests
├── test_client.py       # MODIFIED — add submit/status/cancel method tests
```

### Pattern 1: CacheManager Extension for Tasks Table

Follow the exact pattern used for the `costs` table in `cache.py`. Add a `tasks` table in `_init_tables()`, then add task-specific CRUD methods to the class.

```python
# In CacheManager._init_tables() — follow existing costs table pattern
def _init_tables(self) -> None:
    # ... existing cache and costs tables ...
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

# New task CRUD methods on CacheManager
def save_task(self, task_id: str, endpoint: str, params_json: str | None = None) -> None:
    self._conn.execute(
        "INSERT OR REPLACE INTO tasks "
        "(task_id, endpoint, status, submitted_at, params_json) VALUES (?, ?, ?, ?, ?)",
        (task_id, endpoint, "in_progress", time.time(), params_json),
    )
    self._conn.commit()

def update_task_status(self, task_id: str, status: str, error_message: str | None = None) -> None:
    self._conn.execute(
        "UPDATE tasks SET status = ?, last_polled_at = ?, error_message = ? WHERE task_id = ?",
        (status, time.time(), error_message, task_id),
    )
    self._conn.commit()

def get_task(self, task_id: str) -> dict[str, Any] | None: ...
def list_tasks(self, status_filter: str | None = None) -> list[dict[str, Any]]: ...
```

**Why this location:** CacheManager already owns the SQLite connection. Adding task CRUD here avoids passing the connection to AsyncTaskManager — cleaner than AsyncTaskManager writing SQL directly against a connection it doesn't own.

### Pattern 2: AsyncTaskManager Poll Loop

Linear-to-capped backoff with `try/except KeyboardInterrupt`. The `on_status` callback keeps the poll loop decoupled from the display layer.

```python
class AsyncTaskManager:
    def __init__(self, client: DiscoLikeClient, cache: CacheManager) -> None:
        self._client = client
        self._cache = cache

    def poll(
        self,
        task_id: str,
        on_status: Callable[[str, int, float], None] | None = None,
        initial_interval: float = 3.0,
        interval_step: float = 3.0,
        max_interval: float = 15.0,
        max_elapsed: float = 300.0,
    ) -> dict[str, Any]:
        """Poll until status complete/failed. Returns result dict.
        on_status(status_string, attempt_number, elapsed_seconds) called each iteration.
        """
        elapsed = 0.0
        interval = initial_interval
        attempt = 0

        try:
            while elapsed < max_elapsed:
                result = self._client.task_status(task_id)
                status = result.get("status", "unknown")
                attempt += 1

                self._cache.update_task_status(task_id, status)

                if on_status is not None:
                    on_status(status, attempt, elapsed)

                if status in ("completed", "complete"):
                    self._cache.update_task_status(task_id, "completed")
                    return result
                if status == "failed":
                    error = result.get("error", "Unknown error")
                    self._cache.update_task_status(task_id, "failed", error)
                    raise TaskError(f"Task {task_id} failed: {error}")

                time.sleep(interval)
                elapsed += interval
                interval = min(interval + interval_step, max_interval)

            self._cache.update_task_status(task_id, "timeout")
            raise TaskTimeoutError(
                f"Task {task_id} timed out after {max_elapsed:.0f}s.",
                suggestion="Check task status with: discolike tasks status " + task_id,
            )

        except KeyboardInterrupt:
            self._cache.update_task_status(task_id, "interrupted")
            import sys
            print(
                f"\nTask {task_id} still running on server. "
                f"Resume with: discolike tasks resume {task_id}",
                file=sys.stderr,
            )
            raise SystemExit(0)
```

**Critical detail:** `update_task_status(task_id, "interrupted")` MUST execute before the `print()` in the `except KeyboardInterrupt` block. SQLite write is in-process and fast — no risk of the write failing if the print succeeds.

### Pattern 3: Client Submit Methods

Follow the exact pattern of existing `_post_json()` calls in `client.py`. Submit methods are thin — they call the POST endpoint and return the raw response. No polling.

```python
def discogen_submit(self, params: dict[str, Any]) -> dict[str, Any]:
    """POST /discogen/process -> raw response dict including task_id."""
    if self._dry_run:
        self._cost.estimate("discogen", 0)
        return {"task_id": "dry-run-task-id", "status": "in_progress"}
    return self._post_json("/discogen/process", params)

def validate_icp_submit(self, params: dict[str, Any]) -> dict[str, Any]:
    """POST /validate/icp -> raw response dict including task_id."""
    if self._dry_run:
        self._cost.estimate("validate/icp", 0)
        return {"task_id": "dry-run-task-id", "status": "in_progress"}
    return self._post_json("/validate/icp", params)

def segment_submit(self, params: dict[str, Any]) -> dict[str, Any]:
    """POST /segment -> raw response dict including task_id."""
    if self._dry_run:
        self._cost.estimate("segment", 0)
        return {"task_id": "dry-run-task-id", "status": "in_progress"}
    return self._post_json("/segment", params)

def task_status(self, task_id: str) -> dict[str, Any]:
    """GET /discogen/status/{task_id} -> status dict."""
    return self._get_with_params(f"/discogen/status/{task_id}")

def task_cancel(self, task_id: str) -> dict[str, Any]:
    """DELETE /discogen/cancel/{task_id} -> cancellation confirmation."""
    resp = self._request("DELETE", f"/discogen/cancel/{task_id}")
    result: dict[str, Any] = resp.json()
    return result
```

**Note on `task_cancel`:** The existing `_request()` only handles GET and POST. A DELETE method needs one line added: `elif method.upper() == "DELETE": resp = self._client.delete(url)`.

**Note on `task_status` endpoint:** Per ARCHITECTURE.md and PITFALLS.md Pitfall 7, all three async endpoints (DiscoGen, Validate ICP, Segment) poll via `/discogen/status/{task_id}`. This is an API design decision — the task_id is globally unique and the status endpoint is shared. Do NOT create separate status paths per endpoint type.

### Pattern 4: Pydantic Models for Async Responses

Follow the existing `ConfigDict(extra="allow")` pattern for API response shapes that may evolve.

```python
class TaskSubmitResponse(BaseModel):
    """Response from any async task submission endpoint."""
    model_config = ConfigDict(extra="allow")
    task_id: str
    status: str = "in_progress"

class TaskStatusResponse(BaseModel):
    """Response from task status polling endpoint."""
    model_config = ConfigDict(extra="allow")
    task_id: str | None = None
    status: str
    progress: int | None = None
    results: list[Any] | dict[str, Any] | None = None
    error: str | None = None
    estimated_cost: str | None = None
```

### Pattern 5: Error Classes

Follow the existing `DiscoLikeError` pattern with explicit exit codes.

```python
class TaskError(DiscoLikeError):
    """Async task failed server-side (exit code 1)."""
    exit_code = 1
    suggestion = "Check task status with: discolike tasks status <task_id>"

class TaskTimeoutError(DiscoLikeError):
    """Async task timed out without completing (exit code 1)."""
    exit_code = 1
```

`TaskTimeoutError` is a subclass of `TaskError` for clean `except TaskError` catch patterns.

### Pattern 6: Rich Progress Display

Use `console.status()` as the primary pattern (D-12). The `on_status` callback drives the update.

```python
# In the command layer (Phase 2+) — not in AsyncTaskManager itself
console = Console(stderr=True)

with console.status("[bold green]Submitting task...", spinner="dots") as status:
    response = client.discogen_submit(params)
    task_id = response["task_id"]
    cache.save_task(task_id, "discogen", json.dumps(params))

    def update_display(s: str, attempt: int, elapsed: float) -> None:
        status.update(f"[bold green]Processing... (attempt {attempt}, {elapsed:.0f}s elapsed)")

    result = task_manager.poll(task_id, on_status=update_display)
```

**Degraded TTY fallback:** When `not sys.stderr.isatty()`, skip the spinner entirely and print a line to stderr every N attempts instead. The `on_status` callback handles this transparently — the caller passes a different callback for TTY vs non-TTY. AsyncTaskManager itself does NOT check `isatty()`.

### Anti-Patterns to Avoid

- **Polling inside client methods:** `discogen_submit()` returns the raw response. It never calls `poll()`. Mixing submission with polling in the client breaks the separation of concerns and makes testing harder.
- **Global SIGINT handler:** `signal.signal(SIGINT, handler)` applies globally and has test isolation issues. `try/except KeyboardInterrupt` is scoped to the call stack. Locked in D-09.
- **SQLite write after print on interrupt:** The `except KeyboardInterrupt` block must update SQLite BEFORE printing the stderr message. Reversed order risks the message printing but the SQLite write not completing.
- **Hardcoding `/discogen/status/` path in AsyncTaskManager:** Keep `task_status()` on the client and let AsyncTaskManager call `client.task_status(task_id)`. This keeps the URL logic in one place.
- **Using elapsed += sleep_interval for timeout:** `time.sleep()` can sleep longer than requested on a loaded system. Use `start_time = time.time()` and `elapsed = time.time() - start_time` for accuracy.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQLite connection management | Custom connection pool | Extend existing `CacheManager._conn` | CacheManager already handles connection lifecycle, `_init_tables()` pattern is established |
| HTTP retry on transient failures | Custom retry in poll loop | `DiscoLikeClient._request()` | `_request()` already retries 5xx and connection errors. Poll loop handles `pending` status — these are different concerns |
| Progress bar library | Custom progress display | `rich.console.Console.status()` | Rich is installed. `console.status()` is the established pattern in this codebase |

**Key insight:** The poll loop is NOT a retry-on-failure mechanism. It is a deliberate wait pattern. `_request()` handles transient failures within each poll tick; the poll loop handles the inter-tick spacing. Keep these concerns separate.

## Common Pitfalls

### Pitfall 1: Task ID Lost on Ctrl+C (Critical — Pitfall 3 from PITFALLS.md)
**What goes wrong:** If the `task_id` is only in memory during the poll loop, a Ctrl+C loses it. The job keeps running server-side but the user has no way to resume or cancel it without resubmitting.
**Why it happens:** SQLite write after first poll instead of before.
**How to avoid:** D-03 is the rule: `cache.save_task(task_id, ...)` executes immediately after `client.discogen_submit()` returns, before `task_manager.poll()` is called.
**Warning signs:** `save_task()` is called inside the poll loop or after the first status check.

### Pitfall 2: Validate ICP Shares DiscoGen Status Endpoint (Pitfall 7 from PITFALLS.md)
**What goes wrong:** Building a separate `/validate/status/{task_id}` path for Validate ICP polls.
**Why it happens:** Endpoint naming suggests they'd have separate status URLs.
**How to avoid:** Both DiscoGen and Validate ICP poll via `/discogen/status/{task_id}`. `client.task_status(task_id)` does not vary by endpoint type.
**Warning signs:** Separate status path parameter being passed to `AsyncTaskManager` based on which command submitted the task.

### Pitfall 3: Aggressive Polling on Segment (Pitfall 4 from PITFALLS.md)
**What goes wrong:** Default 3s poll interval hits the 2 req/min segment rate limit, causing 429s inside the poll loop.
**Why it happens:** Using the same poll interval for all three endpoints despite different rate limits.
**How to avoid:** Phase 1 ships the infrastructure with default 3s start / 15s cap. Phase 2 (Segment command) will configure a higher minimum when wrapping this infrastructure for segment jobs. Document the segment rate limit constraint as a note on `AsyncTaskManager.poll()`.
**Warning signs:** No mention of segment rate limit in `async_tasks.py` docstring.

### Pitfall 4: `time.sleep()` Drift Breaks 300s Timeout
**What goes wrong:** Tracking elapsed time by summing `interval` values means actual elapsed time is under-counted when system load extends sleeps past their target.
**Why it happens:** `elapsed += interval` accumulates scheduled time, not wall time.
**How to avoid:** Use `start_time = time.time()` before the loop and `elapsed = time.time() - start_time` inside the loop for the timeout check.
**Warning signs:** Timeout check is `elapsed < max_elapsed` where `elapsed` is a running sum.

### Pitfall 5: DELETE Method Not Handled in `_request()`
**What goes wrong:** `client.task_cancel()` calls `self._request("DELETE", ...)` but `_request()` only has `if method.upper() == "GET"` and `else` (POST). DELETE falls through to the POST branch.
**Why it happens:** Current `_request()` was written before DELETE was needed.
**How to avoid:** Add `elif method.upper() == "DELETE": resp = self._client.delete(url)` to `_request()` before adding `task_cancel()`.
**Warning signs:** `task_cancel()` calls `_post_json()` instead of a DELETE.

### Pitfall 6: Mypy Strict Mode + Callback Typing
**What goes wrong:** `mypy --strict` rejects `Callable[[str, int, float], None] | None` parameter if the import of `Callable` is from `typing` (deprecated in 3.11) instead of `collections.abc`.
**Why it happens:** The project uses `from __future__ import annotations` throughout — but `Callable` still needs the right import.
**How to avoid:** `from collections.abc import Callable` (consistent with how `errors.py` imports it already).
**Warning signs:** Mypy CI failing on `async_tasks.py` with "Cannot determine type of 'Callable'" errors.

## Code Examples

### Submit → Persist → Poll (Correct Order)

```python
# Source: D-03 (locked decision) + client.py _post_json() pattern
def run_discogen(client: DiscoLikeClient, cache: CacheManager, params: dict) -> dict:
    # 1. Submit
    response = client.discogen_submit(params)
    task_id = response["task_id"]

    # 2. Persist BEFORE poll — this is the survivability guarantee
    import json
    cache.save_task(task_id, "discogen", json.dumps(params))

    # 3. Poll
    task_manager = AsyncTaskManager(client, cache)
    return task_manager.poll(task_id)
```

### Correct Elapsed Tracking

```python
# Source: stdlib time module, corrects Pitfall 4
import time

start_time = time.time()
interval = 3.0

while True:
    elapsed = time.time() - start_time  # wall time, not sum of intervals
    if elapsed >= 300.0:
        raise TaskTimeoutError(...)
    # ... poll ...
    time.sleep(interval)
    interval = min(interval + 3.0, 15.0)
```

### Ctrl+C Handler (Correct Order)

```python
# Source: D-09, D-10 (locked decisions)
try:
    while ...:
        # poll loop
except KeyboardInterrupt:
    cache.update_task_status(task_id, "interrupted")  # SQLite first
    print(                                              # stderr second
        f"\nTask {task_id} still running on server. "
        f"Resume with: discolike tasks resume {task_id}",
        file=sys.stderr,
    )
    raise SystemExit(0)
```

### _request() DELETE Support

```python
# Source: client.py _request() — add this elif branch
if method.upper() == "GET":
    resp = self._client.get(url, params=params)
elif method.upper() == "DELETE":
    resp = self._client.delete(url)
else:
    resp = self._client.post(url, json=json_body)
```

### CacheManager Tasks Table Test Pattern

```python
# Source: test_cache.py cost persistence pattern — replicate for tasks
def test_save_and_get_task(cache: CacheManager) -> None:
    cache.save_task("task-123", "discogen", '{"domains": ["example.com"]}')
    task = cache.get_task("task-123")
    assert task is not None
    assert task["task_id"] == "task-123"
    assert task["endpoint"] == "discogen"
    assert task["status"] == "in_progress"

def test_update_task_status(cache: CacheManager) -> None:
    cache.save_task("task-456", "validate/icp")
    cache.update_task_status("task-456", "completed")
    task = cache.get_task("task-456")
    assert task["status"] == "completed"
    assert task["last_polled_at"] is not None
```

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Runtime | Yes | 3.11.3 | — |
| pytest | Test suite | Yes | 9.0.2 | — |
| pytest-cov | Coverage | Yes | installed | — |
| respx | HTTP mocking in tests | Yes | 0.22.0 | — |
| Rich | Progress display | Yes | installed (13.x+) | — |
| SQLite (stdlib) | Task persistence | Yes | stdlib | — |

No missing dependencies. Phase 1 requires zero new installs.

**Note on pre-existing test failures:** 28 tests in `test_workflow.py` and `test_plan_gate.py` are currently failing. These are unrelated to Phase 1 scope (they test workflow and plan gating commands). Phase 1 tests should be written to pass independently. Do NOT fix pre-existing failures as part of this phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `py -m pytest tests/test_cache.py tests/test_client.py tests/test_async_tasks.py -v` |
| Full suite command | `py -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | AsyncTaskManager.poll() drives status lifecycle through complete/failed/timeout | unit | `py -m pytest tests/test_async_tasks.py -x` | No — Wave 0 |
| INFRA-01 | AsyncTaskManager.cancel() calls client.task_cancel and updates SQLite | unit | `py -m pytest tests/test_async_tasks.py::test_cancel -x` | No — Wave 0 |
| INFRA-02 | tasks table created in CacheManager._init_tables() | unit | `py -m pytest tests/test_cache.py::TestTasksPersistence -x` | No — Wave 0 |
| INFRA-02 | save_task() writes before poll() is called | unit | `py -m pytest tests/test_async_tasks.py::test_persist_before_poll -x` | No — Wave 0 |
| INFRA-03 | discogen_submit() POSTs and returns task_id | unit | `py -m pytest tests/test_client.py::TestAsyncSubmit -x` | No — Wave 0 |
| INFRA-03 | validate_icp_submit() POSTs and returns task_id | unit | `py -m pytest tests/test_client.py::TestAsyncSubmit -x` | No — Wave 0 |
| INFRA-03 | segment_submit() POSTs and returns task_id | unit | `py -m pytest tests/test_client.py::TestAsyncSubmit -x` | No — Wave 0 |
| INFRA-03 | task_status() GETs via /discogen/status/{task_id} | unit | `py -m pytest tests/test_client.py::TestTaskStatus -x` | No — Wave 0 |
| INFRA-03 | task_cancel() DELETEs via /discogen/cancel/{task_id} | unit | `py -m pytest tests/test_client.py::TestTaskCancel -x` | No — Wave 0 |
| INFRA-04 | KeyboardInterrupt during poll persists "interrupted" in SQLite then prints to stderr | unit | `py -m pytest tests/test_async_tasks.py::test_ctrl_c_interrupt -x` | No — Wave 0 |
| INFRA-04 | SQLite write happens BEFORE stderr print on interrupt | unit | `py -m pytest tests/test_async_tasks.py::test_interrupt_order -x` | No — Wave 0 |
| INFRA-05 | Poll intervals follow linear-to-capped pattern: 3, 6, 9, 12, 15, 15... | unit | `py -m pytest tests/test_async_tasks.py::test_backoff_sequence -x` | No — Wave 0 |
| INFRA-05 | Hard timeout at 300s raises TaskTimeoutError | unit | `py -m pytest tests/test_async_tasks.py::test_hard_timeout -x` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `py -m pytest tests/test_cache.py tests/test_client.py tests/test_async_tasks.py -x`
- **Per wave merge:** `py -m pytest tests/ -v`
- **Phase gate:** All Phase 1 new tests green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_async_tasks.py` — covers INFRA-01, INFRA-04, INFRA-05 (all AsyncTaskManager behavior)
- [ ] `tests/test_cache.py::TestTasksPersistence` class — covers INFRA-02 (tasks table CRUD)
- [ ] `tests/test_client.py::TestAsyncSubmit` class — covers INFRA-03 submit methods
- [ ] `tests/test_client.py::TestTaskStatus` class — covers INFRA-03 task_status
- [ ] `tests/test_client.py::TestTaskCancel` class — covers INFRA-03 task_cancel + DELETE method in `_request()`

All are new test classes/files. No existing test infrastructure changes needed — `conftest.py` fixtures (mock_config_dir, CliRunner) apply automatically.

## Sources

### Primary (HIGH confidence)
- `src/discolike/cache.py` — CacheManager pattern, `_init_tables()`, cost table as template for tasks table
- `src/discolike/client.py` — `_request()`, `_post_json()`, `_get_with_params()`, dry_run pattern
- `src/discolike/errors.py` — Error hierarchy, `DiscoLikeError`, exit codes
- `src/discolike/types.py` — Pydantic v2 model patterns, `ConfigDict(extra="allow")`
- `.planning/phases/01-async-infrastructure/01-CONTEXT.md` — All locked decisions D-01 through D-12
- `.planning/research/ARCHITECTURE.md` — Component map, data flow, build order, SQL schema
- `.planning/research/PITFALLS.md` — Pitfalls 3, 4, 7 directly relevant to Phase 1
- `.planning/research/STACK.md` — Stdlib polling pattern, confirmed no new deps needed

### Secondary (MEDIUM confidence)
- `.planning/research/SUMMARY.md` — Confirmed Phase 1 scope and build order
- `tests/conftest.py`, `tests/test_cache.py`, `tests/test_client.py` — Test patterns to replicate

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all existing patterns verified by reading source
- Architecture: HIGH — locked decisions + existing code patterns leave no design ambiguity
- Pitfalls: HIGH — based on reading actual source code and locked decisions, not speculation
- Test map: HIGH — direct mapping from requirements to existing test patterns

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable domain — stdlib + existing libs, 30-day window is conservative)
