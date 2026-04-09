# Phase 1: Async Infrastructure - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Shared async task lifecycle for all async endpoints (DiscoGen, Validate ICP, Segment). Jobs survive CLI exit, Ctrl+C is safe, polling uses sane backoff. No new CLI commands in this phase — only the infrastructure that Phase 2+ commands will consume.

</domain>

<decisions>
## Implementation Decisions

### Task Persistence
- **D-01:** Tasks table lives in the same `~/.discolike/cache.db` used by CacheManager — no second database file. CacheManager already manages SQLite connections and table creation.
- **D-02:** Tasks table schema: `task_id TEXT PRIMARY KEY, endpoint TEXT NOT NULL, status TEXT NOT NULL, submitted_at REAL NOT NULL, last_polled_at REAL, params_json TEXT, error_message TEXT`. Minimal — enough to resume/cancel, params_json stores original submission for display. No results storage (results come from API).
- **D-03:** Task persistence happens BEFORE first poll — `task_id` is written to SQLite immediately after the submit API call returns, before any polling begins. This is the core survivability guarantee.

### AsyncTaskManager Design
- **D-04:** AsyncTaskManager is a standalone class (composition, not inheritance) that takes a `DiscoLikeClient` and a `CacheManager` as constructor arguments. Keeps `client.py` focused on HTTP, task manager handles lifecycle.
- **D-05:** Core methods: `submit(endpoint, params) -> task_id`, `poll(task_id, on_status=callback) -> result`, `cancel(task_id) -> bool`, `resume(task_id) -> result`, `list_tasks(status_filter) -> list`.
- **D-06:** `poll()` accepts an `on_status` callback that receives status string updates for Rich display. Simpler than generators, aligns with existing Rich usage patterns.

### Client Submit Methods
- **D-07:** Client gains thin submit methods: `discogen_submit()`, `validate_icp_submit()`, `segment_submit()`. These call the POST endpoint and return the raw response including `task_id`. They do NOT poll — that's AsyncTaskManager's job.
- **D-08:** Client also gains `task_status(task_id)` and `task_cancel(task_id)` methods wrapping the status/cancel API endpoints.

### Signal Handling
- **D-09:** Ctrl+C handled via `try/except KeyboardInterrupt` wrapping the poll loop — no global signal handlers, no atexit hooks. The except block prints task_id to stderr and persists "interrupted" status to SQLite.
- **D-10:** The message format on Ctrl+C: `"\nTask {task_id} still running on server. Resume with: discolike tasks resume {task_id}"` — printed to stderr.

### Polling Backoff
- **D-11:** Linear-to-capped backoff: starts at 3s, increases by 3s each iteration (3, 6, 9, 12, 15, 15, 15...), capped at 15s. Hard timeout at 300s total elapsed.
- **D-12:** Progress display uses `rich.console.Console.status()` spinner with status text updates (e.g., "Polling task abc123... (attempt 4, 12s elapsed)"). Degrades gracefully when not TTY — falls back to periodic stderr lines.

### Claude's Discretion
- File organization within `src/discolike/` — whether AsyncTaskManager goes in a new `tasks.py` or `async_tasks.py`
- Internal helper method naming and decomposition
- Test file organization and fixture structure
- Whether to extend CacheManager with a task-specific method or keep task SQL in AsyncTaskManager

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### API Reference
- `reference/DiscoLike_API_Reference.md` (in leadgrow-hq/archive/mcp-docs/) — Full API docs, all endpoints including async task patterns
- `reference/discolike-field-reference.md` — Field reference for API response shapes
- `reference/discolike-workflow.md` — Workflow patterns and endpoint chaining

### Existing Code
- `src/discolike/client.py` — HTTP client with retry/backoff pattern, must understand before adding submit methods
- `src/discolike/cache.py` — SQLite CacheManager pattern, tasks table extends this
- `src/discolike/types.py` — Pydantic v2 models, new task-related types go here
- `src/discolike/errors.py` — Error hierarchy, new task-related errors extend this

### Project Docs
- `CLAUDE.md` — Architecture overview, tech stack decisions (questionary, no asyncio, etc.)
- `PRD.md` — Full product requirements with user stories

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CacheManager` (`cache.py`): SQLite connection management, table creation pattern. Tasks table follows same pattern.
- `DiscoLikeClient._request()` (`client.py`): Retry/backoff for transient failures. Submit methods use this for the initial POST.
- `CostTracker` (`cost.py`): Per-call cost tracking. Async operations need cost recorded at submit time.
- Error hierarchy (`errors.py`): `APIError`, `AuthError`, `RateLimitError` — extend with `TaskError`, `TaskTimeoutError`.

### Established Patterns
- Sync httpx throughout — no asyncio anywhere. Polling will use `time.sleep()`.
- Pydantic v2 for all API response models — task status responses get a model too.
- Rich for all console output — `console.status()` for polling spinner.
- stderr for progress, stdout for data — polling status goes to stderr.

### Integration Points
- `CacheManager._init_tables()` — add tasks table creation here (or let AsyncTaskManager create its own table on the same connection)
- `DiscoLikeClient.__init__()` — submit/status/cancel methods added as new methods on this class
- `src/discolike/commands/` — Phase 2+ commands will import AsyncTaskManager, but no command changes in Phase 1

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-async-infrastructure*
*Context gathered: 2026-04-08*
