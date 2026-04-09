# Architecture Patterns

**Domain:** CLI extension — async task management, iterative feedback loops, multi-step discovery
**Researched:** 2026-04-08
**Based on:** Full read of existing source (cli.py, client.py, types.py, cost.py, cache.py, output.py, errors.py, commands/discover.py, commands/workflow.py, commands/plan_gate.py) + DiscoLike_API_Reference.md

---

## Existing Architecture (What We're Extending)

The v1 CLI has six clean layers with clear responsibilities:

```
CLI entry (cli.py)
    └── CliContext (dataclass on Click context)
            ├── DiscoLikeClient      → HTTP + retry + cache + cost
            ├── OutputManager        → Rich tables / JSON / CSV
            ├── CostTracker          → per-call + session totals
            └── CacheManager         → SQLite TTL cache

commands/*.py
    └── use get_client(ctx) → call client methods → call output.render()
```

Every command follows the same pattern: collect params → call client → call output.render(). There are no async concerns, no state between API calls, and no interactive loops in the current command layer. The workflow.py commands are the only multi-step sequences, and they manage their own step loops inline.

---

## New Component Map

Three distinct capabilities need to be added. Each has a natural home.

### 1. AsyncTaskManager — `src/discolike/async_tasks.py`

**Responsibility:** All task_id lifecycle: submit → poll → display progress → return results → cancel on interrupt.

DiscoGen, Validate ICP, and Segment all use the same flow:
- POST endpoint returns `{ "task_id": "uuid", "status": "in_progress" }`
- GET `/discogen/status/{task_id}` or `/segment/status/{task_id}` returns `{ "status": "in_progress", "progress": 30, "interim_results": [...] }`
- Completion: `{ "status": "completed", "results": [...] }`
- Cancellation: DELETE `/discogen/cancel/{task_id}`

This is pure infrastructure — no command logic. It belongs at the same layer as CostTracker and CacheManager, not inside any command file.

```
class AsyncTaskManager:
    def __init__(self, client: DiscoLikeClient, output: OutputManager) -> None

    def poll_until_done(
        self,
        task_id: str,
        status_path: str,           # e.g. "/discogen/status/{task_id}"
        cancel_path: str | None,    # e.g. "/discogen/cancel/{task_id}"
        poll_interval: float = 2.0,
        show_interim: bool = True,
    ) -> dict[str, Any]:
        """Block with Rich progress bar until task completes or user Ctrl-C.
        On KeyboardInterrupt, call cancel_path if set, then re-raise as TaskCancelledError.
        Returns completed result dict.
        """

    def record_task(self, task_id: str, command: str) -> None:
        """Persist task_id to SQLite for resume support (GEN-03)."""
```

`AsyncTaskManager` takes the existing `DiscoLikeClient` for HTTP calls and `OutputManager` for progress display. It does NOT own a separate HTTP client. Progress is always on stderr (consistent with current `output.status()` pattern).

**Add to CacheManager** (`cache.py`): a `tasks` table with columns `task_id TEXT, command TEXT, status_path TEXT, cancel_path TEXT, created_at REAL`. This enables resume: `discolike discogen resume <task_id>`.

**Add to CliContext** (`cli.py`): `task_manager: AsyncTaskManager | None = None`, lazily initialized alongside the client.

### 2. QueryPlan — `src/discolike/query_plan.py`

**Responsibility:** Model + presenter for the OLM feedback loop state. Bridges `X-Applied-Filters` from the discover response into a reviewable, editable, resubmittable plan.

The feedback loop is built from two existing API primitives:
- `X-Applied-Filters` response header: JSON blob showing what the API actually used (extracted ICP text, merged phrase matches, inferred industry groups, normalized filters)
- Explicit param resubmission: on confirmation, rebuild the filter dict from the displayed plan and resubmit with `auto_icp_text=False` / `auto_phrase_match=False` (i.e., use explicit params, not re-derive)

```python
class QueryPlan(BaseModel):
    """The interpreted query plan extracted from X-Applied-Filters."""
    icp_text: str | None = None
    phrase_matches: list[str] = []
    industry_groups: list[str] = []
    filters: dict[str, Any] = {}           # all explicit filters applied
    iteration: int = 1
    result_count: int = 0                  # from last discover call
    cost_so_far: Decimal = Decimal("0")
```

```python
class QueryPlanPresenter:
    """Renders QueryPlan to stderr and collects user adjustments."""

    def display(self, plan: QueryPlan, output: OutputManager) -> None:
        """Rich-formatted plan summary on stderr."""

    def prompt_adjustments(self, plan: QueryPlan) -> QueryPlan | None:
        """Interactive: show plan, collect adjustments, return updated plan.
        Returns None if user confirms (ready to run full query).
        Returns updated QueryPlan if user wants another iteration.
        Skipped entirely when stdout is not a TTY (agent mode).
        """
```

The critical TTY check: when `--json` or stdout is not a TTY, skip the interactive loop entirely and output the plan as JSON so an agent can review and resubmit with `--confirm` and explicit params. This is LOOP-04.

### 3. New Command Files

| File | Commands | Wraps |
|------|----------|-------|
| `commands/discogen.py` | `discolike discogen`, `discolike discogen personas` | `/discogen/process`, `/discogen/process-personas` |
| `commands/validate.py` | `discolike validate` | `/validate/icp` |
| `commands/segment.py` | `discolike segment` | `/segment` |
| `commands/llm_providers.py` | `discolike llm-providers list/add/remove` | `/discogen/models` + config |
| `commands/search_providers.py` | `discolike search-providers list/add/remove` | config |

Each of these commands follows the exact same pattern as existing commands: get params → validate → call client → pass task_id to AsyncTaskManager.poll_until_done() → call output.render().

**Changes to `commands/discover.py`:** Add `--confirm` flag (LOOP-03). When set:
1. Capture `X-Applied-Filters` from response headers (requires client.discover() to expose raw response headers — see client changes below).
2. Build a `QueryPlan` from the filters.
3. Call `QueryPlanPresenter.prompt_adjustments()`.
4. Loop: adjust → rebuild filters → resubmit discover → repeat until user confirms.
5. On confirmation, run full TAM query (increased max_records).

---

## Client Changes Required

`DiscoLikeClient.discover()` currently discards response headers — it returns `DiscoverResult` only. Two changes needed:

**Option A (preferred):** Return a richer tuple or new model:

```python
class DiscoverResponse(BaseModel):
    result: DiscoverResult
    applied_filters: dict[str, Any] = {}   # from X-Applied-Filters header
```

`client.discover()` returns `DiscoverResponse`. Existing callers access `.result` for the current `DiscoverResult`. This is backwards-compatible with one extra attribute access.

**Option B (simpler but leakier):** Pass `applied_filters` as an out-param or expose a `last_applied_filters` property on the client. Worse design — avoid.

**New client methods for async endpoints:**

```python
def discogen_submit(self, domains: list[str], prompt: str, **kwargs) -> str:
    """POST /discogen/process -> task_id"""

def discogen_personas_submit(self, persona_ids: list[str], prompt: str, **kwargs) -> str:
    """POST /discogen/process-personas -> task_id"""

def validate_icp_submit(self, domains: list[str], icp_text: str, **kwargs) -> str:
    """POST /validate/icp -> task_id"""

def segment_submit(self, csv_path: Path, **kwargs) -> str:
    """POST /segment (multipart) -> task_id"""

def task_status(self, status_path: str) -> dict[str, Any]:
    """GET {status_path} -> status dict. Used by AsyncTaskManager."""

def task_cancel(self, cancel_path: str) -> dict[str, Any]:
    """DELETE {cancel_path} -> cancellation confirmation."""
```

All submit methods return `task_id` only. `AsyncTaskManager` handles all subsequent polling via `task_status()` and `task_cancel()`. This keeps the client as a thin HTTP wrapper and the polling logic centralized in `AsyncTaskManager`.

---

## Data Flow: Feedback Loop

```
User: discolike discover --domain stripe.com --auto-icp --auto-phrases --confirm

  1. discover.py: collect_filters() → filters dict (auto_icp_text=True, auto_phrase_match=True)

  2. client.discover() → POST /discover
     Response: DiscoverResponse {
       result: DiscoverResult (10 validation records),
       applied_filters: {              <- from X-Applied-Filters header
         "icp_text": "Payment processing platforms for SaaS...",
         "phrase_match": ["payment gateway", "API-first billing"],
         "industry_groups": ["Financial Technology", "SaaS"],
         "country": ["US"],
         "employee_range": "10,500"
       }
     }

  3. QueryPlan built from applied_filters
     plan.iteration = 1, plan.result_count = 847, plan.cost_so_far = $0.05

  4. QueryPlanPresenter.display() → stderr table showing extracted filters

  5. stdout.isatty()?
     YES (interactive): QueryPlanPresenter.prompt_adjustments()
       User sees: "ICP text: Payment processing..."
       User types: "remove 'API-first billing', add employee_range 10-200"
       Returns updated QueryPlan with modified filters

     NO (agent): Output plan as JSON to stdout with exit code 0
       Agent reviews, adjusts params, resubmits with explicit --icp-text "..." flags
       discover called again with --confirm (no auto-derivation)

  6. Loop back to step 2 with updated filters (auto_icp=False now, explicit params)

  7. User/agent confirms → run full query (--max-records 500 or configured)

  8. Output final DiscoverResult via output.render()
```

Rate-limit awareness: Each iteration consumes one discover call (5/min on Starter). `CostTracker.session_calls` already accumulates across iterations. The feedback loop should display iteration count and cumulative cost after each round so the user can decide when to stop refining.

---

## Data Flow: Async Tasks (DiscoGen, Validate, Segment)

```
User: discolike discogen --domains domains.txt --prompt "What is their main use case?"

  1. discogen.py: parse params, read domains from file

  2. client.discogen_submit(domains, prompt) → task_id = "abc-123"

  3. AsyncTaskManager.poll_until_done(
       task_id = "abc-123",
       status_path = "/discogen/status/abc-123",
       cancel_path = "/discogen/cancel/abc-123"
     )
     - Renders Rich progress bar on stderr (0% → 100%)
     - Every poll: displays interim_results if show_interim=True
     - Ctrl-C: calls cancel_path, prints "Task cancelled", exits code 0
     - On completion: returns result dict

  4. output.render(result) → table / JSON / CSV

  5. cost_tracker records total (estimated_cost from API response + query fee)
```

The `AsyncTaskManager.poll_until_done()` method is identical for DiscoGen, Validate, and Segment. The only differences are the status_path and cancel_path strings. Both segment and validate use the `/discogen/status/{task_id}` endpoint per the API reference (Validate ICP notes: "Poll GET /discogen/status/{task_id}").

---

## Component Boundaries

| Component | File | Responsibility | Does NOT own |
|-----------|------|---------------|--------------|
| `DiscoLikeClient` | `client.py` | HTTP calls, retry, cache, cost tracking | Polling loops, display, interactivity |
| `AsyncTaskManager` | `async_tasks.py` | Poll → progress → cancel lifecycle | HTTP implementation, command logic |
| `QueryPlan` | `query_plan.py` | Data model for feedback loop state | HTTP, display |
| `QueryPlanPresenter` | `query_plan.py` | Display + interactive adjustment | HTTP, state mutation |
| `CacheManager` | `cache.py` | SQLite TTL cache + cost persistence + task persistence | Everything else |
| `OutputManager` | `output.py` | Rich/JSON/CSV rendering | Progress bars (those go to AsyncTaskManager) |
| `commands/*.py` | `commands/` | Param collection, orchestration | Any business logic |

Note on progress bars: The current `workflow.py` uses `rich.progress.Progress` inline. `AsyncTaskManager` should centralize the progress bar for async tasks specifically. Synchronous multi-step workflows (like `workflow discover`) can continue managing their own step-by-step status messages inline — no need to refactor those.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Inline Polling in Command Files
**What:** Each of discogen.py, validate.py, segment.py implements its own poll loop with its own progress bar.
**Why bad:** Three implementations of the same loop. Rate limit handling, Ctrl-C behaviour, and interim result display diverge immediately.
**Instead:** All three call `AsyncTaskManager.poll_until_done()`. Differences expressed as parameters (status_path, cancel_path, show_interim).

### Anti-Pattern 2: Feedback Loop State in CliContext
**What:** Storing `current_query_plan`, `loop_iteration`, etc. on `CliContext`.
**Why bad:** CliContext is shared across the entire CLI session. Feedback loop state is scoped to a single discover invocation. Mixing them causes confusion if multiple invocations happen.
**Instead:** `QueryPlan` is a local variable inside the `discover` command function. It does not live on CliContext. `AsyncTaskManager` can live on CliContext since it's stateless infrastructure.

### Anti-Pattern 3: Mutating Applied Filters Back to Auto-Mode
**What:** On each feedback loop iteration, re-send `auto_icp_text=True` so the API re-derives.
**Why bad:** Re-derivation makes the loop non-convergent. Each iteration gets a fresh AI interpretation, so manual adjustments from the previous round are overwritten.
**Instead:** After the first iteration, always send explicit params derived from the last `QueryPlan`. `auto_icp_text=False`, `auto_phrase_match=False`, explicit `icp_text` and `phrase_match` values.

### Anti-Pattern 4: Blocking the Full TAM Query in Feedback Mode
**What:** Each feedback iteration runs with full `max_records`.
**Why bad:** 5 req/min rate limit on Starter. A 5-iteration loop using 500 records each would hit the limit immediately and cost ~$0.50+ in refinement alone.
**Instead:** Feedback iterations use a fixed small count (default 10, same as validation discover in workflow.py). Full TAM query only runs on explicit confirmation.

---

## SQLite Schema Additions

Two new tables in `~/.discolike/cache.db`:

```sql
-- Task persistence for resume support
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    command TEXT NOT NULL,           -- "discogen", "validate", "segment"
    status_path TEXT NOT NULL,
    cancel_path TEXT,
    status TEXT NOT NULL DEFAULT 'in_progress',
    created_at REAL NOT NULL,
    completed_at REAL
);

-- Query plan history for feedback loop audit trail
CREATE TABLE IF NOT EXISTS query_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,        -- random UUID per discover --confirm invocation
    iteration INTEGER NOT NULL,
    filters_json TEXT NOT NULL,      -- serialized filters dict
    result_count INTEGER,
    cost_total TEXT,
    created_at REAL NOT NULL
);
```

`query_plans` is optional for MVP but enables `discolike costs` to show feedback loop iteration costs explicitly, and provides an audit trail for agent sessions.

---

## Build Order

Dependencies flow bottom-up. Build in this order:

**Phase 1: Infrastructure**
1. `async_tasks.py` — `AsyncTaskManager` (depends on: existing client.task_status + task_cancel, OutputManager)
2. `client.py` additions — `discogen_submit`, `validate_icp_submit`, `segment_submit`, `task_status`, `task_cancel`
3. `cache.py` additions — `tasks` table migration
4. `types.py` additions — `DiscoverResponse`, `DiscoGenResult`, `ValidateIcpResult`, `SegmentResult`

These have no user-facing changes yet. Testable in isolation.

**Phase 2: Async Commands**
5. `commands/discogen.py` — uses AsyncTaskManager from Phase 1
6. `commands/validate.py` — same pattern
7. `commands/segment.py` — same pattern + plan gate (Pro+)
8. Register in `cli.py`

Each command is independently testable. No dependencies between them.

**Phase 3: Feedback Loop**
9. `query_plan.py` — `QueryPlan` model + `QueryPlanPresenter`
10. `client.py` — expose `applied_filters` in `DiscoverResponse`
11. `commands/discover.py` — add `--confirm` flag, loop logic

This is the most complex phase. Depends on Phase 1 client changes (DiscoverResponse). Isolated to discover.py — does not touch other commands.

**Phase 4: BYOM/BYOS Config**
12. `commands/llm_providers.py`
13. `commands/search_providers.py`
14. Add `integration_id` and `search_provider_id` params to discogen.py and validate.py

These are additive and do not affect earlier phases.

**Phase 5: Skill**
15. `lg-research/skills/discolike-discovery-v2/SKILL.md` — multi-dimensional discovery skill
16. Updates to existing `discolike-discovery` skill or replacement

The skill depends on all CLI commands existing. Build last.

---

## Files Created/Modified Summary

| Action | File | What |
|--------|------|------|
| New | `src/discolike/async_tasks.py` | AsyncTaskManager class |
| New | `src/discolike/query_plan.py` | QueryPlan model + QueryPlanPresenter |
| Modified | `src/discolike/client.py` | DiscoverResponse, submit methods, task_status, task_cancel |
| Modified | `src/discolike/cache.py` | tasks + query_plans tables |
| Modified | `src/discolike/types.py` | DiscoverResponse, result models for async endpoints |
| Modified | `src/discolike/cli.py` | Register new commands, add task_manager to CliContext |
| Modified | `src/discolike/errors.py` | TaskCancelledError (exit code 0), TaskTimeoutError (exit code 1) |
| Modified | `src/discolike/commands/discover.py` | --confirm flag, feedback loop integration |
| New | `src/discolike/commands/discogen.py` | discogen + discogen personas commands |
| New | `src/discolike/commands/validate.py` | validate command |
| New | `src/discolike/commands/segment.py` | segment command |
| New | `src/discolike/commands/llm_providers.py` | llm-providers subcommands |
| New | `src/discolike/commands/search_providers.py` | search-providers subcommands |
| New | `lg-research/skills/discolike-discovery-v2/SKILL.md` | Interactive multi-dimensional skill |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Existing architecture patterns | HIGH | Full source read — clear, consistent patterns |
| API async task shape | HIGH | API reference explicitly documents task_id flow for all three endpoints |
| X-Applied-Filters header | HIGH | API reference documents it as a response header on /discover |
| Feedback loop as explicit resubmit | HIGH | PROJECT.md explicitly states this design decision |
| QueryPlanPresenter interactive prompt | MEDIUM | Click prompt patterns are well-established; specific UX TBD at implementation |
| Segment uses same /discogen/status endpoint | HIGH | API reference states "Poll GET /discogen/status/{task_id}" for Validate ICP; Segment uses /segment/status/{task_id} per reference |
