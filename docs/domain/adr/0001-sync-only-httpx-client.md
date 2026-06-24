# ADR-0001: Sync-Only httpx Client — No asyncio

## Status

Accepted

## Context

The DiscoLike CLI is a terminal tool invoked interactively by a human or a script. The primary use case is a single user running one command at a time. The CLI also needs to implement "async task" polling — where the API processes a long-running job server-side and the client polls for completion.

Two implementation approaches were considered:
1. **asyncio + `httpx.AsyncClient`**: Natural fit for concurrent HTTP, but adds complexity (event loop management, `async/await` propagation through Click commands, Windows `ProactorEventLoop` quirks, and a secondary runtime dependency surface).
2. **Sync `httpx.Client` + `while` + `time.sleep`**: Simpler. No event loop. No async context managers in Click commands. The "async task" label refers to the server-side behavior, not client-side concurrency — a polling loop with `time.sleep` is sufficient.

## Decision

Use `httpx` in sync mode only. The `httpx.Client` is instantiated once per CLI invocation and closed on exit. Async task polling (discogen, validate, segment) uses a blocking `while True` loop with `time.sleep` in `AsyncTaskManager.poll()`.

No `asyncio`, no `AsyncClient`, no `await` anywhere in the codebase.

## Consequences

**Good:**
- Click command functions are plain synchronous Python — no `async def`, no `await`.
- No Windows event loop edge cases (`ProactorEventLoop`, subprocess interaction).
- Retry/backoff logic in `_request()` is straightforward `time.sleep` without asyncio cancellation concerns.
- Test mocking is simpler: `respx` mocks sync httpx without needing `anyio` or `pytest-asyncio`.
- `KeyboardInterrupt` during polling works predictably — caught in a regular `try/except`, not entangled with asyncio cancellation.

**Bad / Tradeoffs:**
- Cannot run multiple API calls concurrently within a single command invocation. The `append` and `workflow` commands that process multiple domains must do so sequentially.
- The "async task" naming (`async_tasks.py`, `AsyncTaskManager`) is potentially confusing — it refers to the API's asynchronous job model, not Python's asyncio. This is documented explicitly in `CLAUDE.md` and the class docstring.
- If a future command genuinely needs concurrent HTTP (e.g., enriching 1000 domains in parallel), this decision must be revisited. The right move at that point is to add an optional async pathway, not to retrofit the entire CLI.
