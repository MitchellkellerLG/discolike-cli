# Phase 3: OLM Feedback Loop - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning
**Mode:** --auto (all gray areas resolved with recommended defaults)

<domain>
## Phase Boundary

Add an opt-in interactive review/adjust/resubmit cycle to the existing `discover` command via a new `--confirm` flag. The loop sits between the user (or Claude Code agent) and DiscoLike's OLM (query interpreter): after the first call, parse the `X-Applied-Filters` response header into a structured `QueryPlan`, display it, let the user adjust, then resubmit with explicit params so the OLM cannot re-derive and overwrite manual corrections. Iterations continue until the user explicitly confirms "run full TAM query" or aborts. All cost is visible up front and cumulatively; TTY is guarded so pipe/agent workflows can't hang.

**Scope anchor:** `discover --confirm` only. No other commands. No segment. No provider config. No async task manager (discover is synchronous — each iteration is one `GET /discover` call).

**Backwards compatibility:** `discover` without `--confirm` behaves identically to today. Zero regression risk on the existing one-shot path.

</domain>

<decisions>
## Implementation Decisions

### QueryPlan Data Model (LOOP-01)
- **D-01:** New Pydantic v2 model `QueryPlan` in `src/discolike/types.py`. Fields mirror the `X-Applied-Filters` header shape: `lookalike_text: str | None`, `icp_text: str | None`, `phrase_matches: list[str]`, `negate_phrase_matches: list[str]`, `industry_groups: list[dict]` (name + score), `categories: list[str]`, `countries: list[str]`, `states: list[str]`, `employee_range: tuple[int, int] | None`, `min_similarity: int | None`, `raw: dict[str, Any]` (the unparsed header for forward compatibility). Unknown keys preserved in `raw` via Pydantic `model_config = ConfigDict(extra="allow")`.
- **D-02:** `client.discover()` is modified to capture `X-Applied-Filters` and `X-Total-Count` from `resp.headers`, parse the JSON, and attach a `QueryPlan` instance to the existing `DiscoverResult` via a new `query_plan: QueryPlan | None` field. **Non-breaking** — existing callers that ignore `query_plan` keep working.
- **D-03:** Header parsing is fault-tolerant: if `X-Applied-Filters` is missing, malformed, or not JSON, log a warning to stderr and build a fallback `QueryPlan` from the submitted filters dict. The loop must never crash on missing server metadata — degrade gracefully to "manual mode."

### QueryState (LOOP-10)
- **D-04:** New module `src/discolike/query_state.py` containing:
  - `QueryState` dataclass: `filters: dict[str, Any]`, `query_plan: QueryPlan`, `locked_fields: set[str]`, `iterations: list[IterationRecord]`, `max_iterations: int`, `cumulative_cost_usd: float`.
  - `IterationRecord` dataclass: `iteration: int`, `filters_sent: dict`, `query_plan_returned: QueryPlan`, `record_count: int`, `cost_usd: float`, `timestamp: float`.
  - Helper methods: `lock_field(name)`, `apply_edit(field, value)`, `diff_against_previous() -> list[FieldDiff]`, `to_json_dict() -> dict` (for --json output).
- **D-05:** QueryState is **in-memory only** — it lives for the life of a single `discover --confirm` invocation. No SQLite persistence (Phase 1's `tasks` table is for async jobs; discover is synchronous, so there's nothing to resume). If the user Ctrl+C's mid-loop, the iterations are lost and they rerun. This keeps scope tight and avoids a second persistence layer.
- **D-06:** "Locked" means the field was manually edited by the user in a prior iteration. On resubmission, locked fields are sent as explicit params; the server-side `auto_icp_text` and `auto_phrase_match` flags are forced to `false` so the OLM cannot re-derive and overwrite them (LOOP-03). Unlocked fields flow through as whatever the OLM returned last iteration, not the original seed — this is the "merge-not-replace" behavior of LOOP-10.

### Interactive UX — questionary (LOOP-02)
- **D-07:** New module `src/discolike/query_loop.py` owns the interactive loop. Entry point: `run_query_loop(client, initial_filters, max_records, max_iterations, output) -> DiscoverResult`. Called from `discover` command when `--confirm` is set and the TTY guard passes.
- **D-08:** Per-iteration UI flow:
  1. Run `client.discover(filters, max_records=QUICK_SAMPLE)` (small sample, see D-16)
  2. Render QueryPlan in a Rich Panel with sectioned Table (see D-11)
  3. If iteration > 1, render diff view (see D-13)
  4. Render cumulative cost table (see D-12)
  5. Present questionary `select` main menu:
     - `🚀 Run full TAM query (max_records=N)` — exit loop, run final discover with user-specified `--max-records`, return result
     - `✏️  Edit query plan` — drop into edit sub-menu
     - `📊 Show record sample` — display the sample records returned this iteration
     - `❌ Abort` — exit with no final query, return empty result and exit code 0
  6. If "Edit", sub-menu: questionary `select` listing editable fields (see D-09); each choice opens the right prompt (text, checkbox, etc.)
  7. After edit, loop back to step 1 (bumps iteration counter, increments cumulative cost)
- **D-09:** Editable fields in v1 (ranked by user value):
  1. `icp_text` — questionary `text` prompt, pre-filled with current value; empty clears
  2. `phrase_matches` — questionary `checkbox` with current phrases; unchecked = dropped; separate text prompt to add new phrases
  3. `categories` — questionary `checkbox` from CATEGORIES constant
  4. `countries` — questionary `text` (comma-separated ISO codes)
  5. `employee_range` — questionary `text` (format "min,max")
  6. `min_similarity` — questionary `text` (int 0-99)

  Any field not in this list is displayed as read-only in the QueryPlan panel with a `(not editable in v1)` note. Advanced fields like `negate_*`, `tech_stack`, `variance`, `consensus` are deferred (see Deferred Ideas). This keeps the first release's UI surface small while covering 80% of what users will actually tune.

### QueryPlan Display (LOOP-01 visual)
- **D-10:** Use Rich `Panel` wrapping a Rich `Table` — NOT a Tree. Tables align better with the existing output style and handle wide terminals cleanly. One table, columns: `Field | Value | Source`. `Source` column shows `auto` (OLM-derived), `🔒 locked` (manually edited), or `seed` (came from user's initial CLI args unchanged).
- **D-11:** Sections (as Table rows with section separators, not nested tables):
  1. **Query intent** — `lookalike_text`, `icp_text`
  2. **Phrase matching** — `phrase_matches`, `negate_phrase_matches`
  3. **Classification** — `categories`, `industry_groups` (name+score)
  4. **Geo** — `countries`, `states`
  5. **Size** — `employee_range`, `min_similarity`
  6. **Raw (advanced)** — any keys in `query_plan.raw` not captured above, collapsed into one row

### Cost Display (LOOP-06)
- **D-12:** Cumulative cost rendered as a compact Rich Table before each iteration's main menu:
  ```
  ┌─────────────┬──────────┬──────────┐
  │ Iteration   │ Records  │ Cost     │
  ├─────────────┼──────────┼──────────┤
  │ 1           │ 10       │ $0.001   │
  │ 2           │ 10       │ $0.001   │
  ├─────────────┼──────────┼──────────┤
  │ Total so far│          │ $0.002   │
  │ Next (est)  │ 10       │ $0.001   │
  │ Final TAM   │ ~2,500   │ $0.25    │
  └─────────────┴──────────┴──────────┘
  ```
- **D-13:** Reuse existing `CostTracker` from `src/discolike/cost.py`. Read `cost_tracker.last_call` after each iteration (append to `IterationRecord.cost_usd`). Use `cost_tracker.estimate("discover", max_records)` for the "Next" and "Final TAM" rows — same method the `--dry-run` path already uses. **No new cost infrastructure.**

### Diff View (LOOP-08)
- **D-14:** `QueryState.diff_against_previous()` returns a list of `FieldDiff(field, previous, current, change_type)` where change_type is one of `added | removed | modified`. Rendered as a Rich Table: `Field | Previous | Current` with color coding (green=added, red=removed, yellow=modified). Only displayed when iteration > 1, and only includes fields that actually changed. For list fields, show set diff ("+phrase_x, -phrase_y") rather than dumping whole lists. No external diff library.

### Convergence Gate (LOOP-04, LOOP-07)
- **D-15:** The loop exits only via one of:
  1. User selects `🚀 Run full TAM query` from the main menu → loop exits, command runs one final `client.discover(filters=state.final_filters, max_records=user_max_records)` and renders the result
  2. User selects `❌ Abort` → loop exits, empty result, command exits 0
  3. Iteration count hits `--max-iterations` (default 3) → questionary `confirm` prompt "Max iterations reached. Run final TAM query with current plan?" — yes runs TAM, no aborts. **No silent convergence.**
- **D-16:** During the loop, iterations use a small **sample size** (default 10 records, overridable via new `--sample-records` flag) to keep cost low. The final TAM query uses the user's `--max-records` value (existing flag, default 10). Rationale: iteration should be cheap; only the final run pays for the full result set. Mention this clearly in the cost table.

### TTY Guard (LOOP-09)
- **D-17:** Guard fires at the top of the `discover` command body, **before** any API calls:
  ```python
  if confirm and not sys.stdin.isatty():
      raise click.UsageError(
          "--confirm requires an interactive terminal. "
          "For agent/pipe workflows, use --json to get the structured "
          "query plan and run discover iterations programmatically with "
          "explicit params (see docs/agent-loop.md)."
      )
  ```
  Error message explicitly points agents at the LOOP-05 alternative so they aren't left guessing. Exit code: 2 (UsageError default — matches PRD US-016 exit code conventions).

### JSON Query Plan (LOOP-05)
- **D-18:** When `--json` is set (with or without `--confirm`), the output always includes `query_plan` (the parsed `X-Applied-Filters` for the most recent call). This gives agents a one-shot path: call `discover --json`, read `query_plan`, mutate, call again with explicit params. **This is the agent-in-the-loop pattern** — no interactive TUI, but full structural visibility.
- **D-19:** When `--confirm` IS set (TTY mode) AND `--json` is set, the final JSON output includes the full iteration history: `{result: {...}, query_plan: {...}, iterations: [...], cumulative_cost: 0.0025, converged: true|false}`. This lets automated tests and logging capture the entire loop trace.

### Command Surface (new flags on `discover`)
- **D-20:** Three new Click options added to `discover` command (no changes to `count`):
  - `--confirm` (bool flag, default False) — opt into the feedback loop
  - `--max-iterations` (int, default 3) — cap on loop iterations
  - `--sample-records` (int, default 10) — record count during iteration (final TAM uses `--max-records`)
  The existing `discovery_filters` decorator stays untouched — these three are discover-specific.

### Claude's Discretion
- Internal helper decomposition within `query_loop.py` (render_plan, render_cost, render_diff, handle_edit, etc.)
- Exact Rich color palette for diff view (follow existing OutputManager conventions)
- Test fixture structure — whether to mock `questionary` via monkeypatch or use its `.unsafe_ask()` / pytest plugin
- Whether `FieldDiff` is a dataclass or NamedTuple
- Precise phrasing of Panel titles and menu labels (keep concise, match existing CLI voice)
- Whether to extract the QueryPlan render into `output.py` or keep it colocated in `query_loop.py` (lean toward colocated since it's loop-specific)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### API Reference (source of truth for QueryPlan shape)
- `../leadgrow-hq/archive/mcp-docs/DiscoLike_API_Reference.md` §Response Headers lines 221-227 — `X-Applied-Filters` header definition (JSON object showing extracted/merged filters). **This is the entire source of QueryPlan data.**
- `../leadgrow-hq/archive/mcp-docs/DiscoLike_API_Reference.md` §Discover Parameters lines 140-220 — full filter parameter list, including `auto_icp_text` and `auto_phrase_match` flags that must be forced `false` on resubmissions
- `reference/discolike-field-reference.md` — field definitions for the records returned (not the query plan, but useful when rendering sample records)
- `reference/discolike-workflow.md` — workflow patterns for iterative refinement

### Existing Code (must understand before modifying)
- `src/discolike/commands/discover.py` — current `discover` command (270 lines), `discovery_filters` decorator, `collect_filters()` helper. Modified to add `--confirm`, `--max-iterations`, `--sample-records` flags and loop dispatch.
- `src/discolike/client.py` lines 275-304 — current `discover()` method throws away `resp.headers`. Modified to capture `X-Applied-Filters`, parse into `QueryPlan`, attach to `DiscoverResult`.
- `src/discolike/types.py` — Pydantic v2 models. New `QueryPlan` model added here. `DiscoverResult` gains `query_plan: QueryPlan | None` field.
- `src/discolike/cost.py` — `CostTracker` with `record_call`, `estimate`, `last_call`, `session_total`. Reused as-is for cumulative cost display.
- `src/discolike/output.py` — `OutputManager` for table/JSON/CSV rendering. Query plan JSON serialization uses existing patterns.
- `src/discolike/errors.py` — error hierarchy. New loop-specific error class may extend this (e.g., `QueryLoopAbortedError`) or the loop can exit normally via sentinel return.
- `src/discolike/cli.py` — `_get_context()`, `get_client()` helpers used by all commands.

### Phase 1 & 2 Context (prior decisions that apply)
- `.planning/phases/01-async-infrastructure/01-CONTEXT.md` — Phase 1 decisions D-01 through D-12. **NOTE: Phase 1's AsyncTaskManager is NOT used in Phase 3 — discover is synchronous.** Listed only so the planner doesn't mistakenly wire it in.
- `.planning/phases/02-async-commands/02-CONTEXT.md` — Phase 2 established patterns for Click option design (D-09, D-10), cost display (D-07), Rich output (D-06). Phase 3 follows the same style.

### Project Docs
- `CLAUDE.md` — Tech stack locked (questionary 2.1.1, no asyncio, Rich, Pydantic v2), key patterns (stderr for progress, stdout for data, exit codes 0-6, cost on every call)
- `PRD.md` — full product requirements with user stories (esp. US-016 for exit codes)
- `.planning/ROADMAP.md` §Phase 3 — goal statement, 6 success criteria, LOOP-01..10 requirements mapping

### Library Docs (fetch on demand during planning)
- questionary 2.1.1 — for `select`, `checkbox`, `text`, `confirm` prompt APIs. Use `mcp__context7__*` to pull current docs if planner needs specifics.
- Rich Panel + Table — already used throughout codebase; reference existing usage in `src/discolike/output.py` rather than external docs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DiscoLikeClient.discover()` (`client.py:275`) — existing sync discover call. Minimal modification: capture `resp.headers`, parse `X-Applied-Filters`, attach QueryPlan. Method signature unchanged.
- `CostTracker` (`cost.py`) — `record_call`, `estimate`, `session_total`, `last_call` all already there. Loop reads these; no new methods needed.
- `discovery_filters` decorator (`commands/discover.py:15`) — shared Click options for all discovery filter params. Reused by the loop's "edit" flow to know which fields are valid filter keys.
- `collect_filters()` (`commands/discover.py:163`) — builds API filter dict from Click kwargs. Loop uses this once for the initial filter build, then mutates the resulting dict directly via `QueryState.apply_edit()`.
- `OutputManager` (`output.py`) — handles table/JSON/CSV rendering with cost footer. The loop only calls it for the final TAM result; iteration UI is rendered directly via Rich (colocated in `query_loop.py`).
- `handle_errors` decorator (`errors.py`) — wraps command in standard error handling. Loop errors propagate through this normally.

### Established Patterns
- Sync httpx throughout — no asyncio. Loop uses blocking questionary prompts and blocking client calls. ✅
- Pydantic v2 for all API models — `QueryPlan` follows the pattern. ✅
- Rich for all console output — `Panel`, `Table`, `Console`. ✅
- stderr for progress/prompts, stdout for data — questionary writes to stderr by default; final TAM result goes to stdout via OutputManager. ✅
- `--json` flag on every data-returning command — honored, includes full iteration trace when `--confirm` is also set. ✅
- One file per logical unit in `src/discolike/` — new files: `query_state.py`, `query_loop.py`. `commands/discover.py` stays a single file.

### Integration Points
- `src/discolike/commands/discover.py` — add 3 new Click options, add `if confirm: dispatch to query_loop` branch before the existing `client.discover()` call
- `src/discolike/client.py:275-304` — modify `discover()` method to capture headers and build QueryPlan
- `src/discolike/types.py` — add `QueryPlan` model, extend `DiscoverResult` with `query_plan` field
- `src/discolike/query_loop.py` (NEW) — entry point `run_query_loop()`, all render + prompt logic
- `src/discolike/query_state.py` (NEW) — `QueryState`, `IterationRecord`, `FieldDiff` dataclasses + diff logic
- `pyproject.toml` — add `questionary>=2.1,<3.0` to dependencies (first actual use in codebase — confirms CLAUDE.md stack decision)

### Constraints / Gotchas
- `questionary` and `Rich` both own the terminal. Rendering a Rich Live region during a questionary prompt will cause output interleaving. **Pattern:** render Rich output first (panels, tables), THEN hand control to questionary. Never render Rich while a prompt is open. Already noted in CLAUDE.md under "Pitfall: Rich + questionary Output Interleaving."
- `client.discover()` signature change must stay backwards compatible — attaching `query_plan` to `DiscoverResult` is additive, but if any other code reads `DiscoverResult` via `.model_dump()` and serializes to a fixture, the fixtures will need updating. Grep `DiscoverResult` usage before planning.
- Rate limit is 5 req/min on Starter plan. A 3-iteration loop plus final TAM = 4 calls. Well under the limit, but concurrent loops (agents) could hit it. Not a Phase 3 problem — document in docstring, defer actual rate-limit handling to agent side.

</code_context>

<specifics>
## Specific Ideas

- **Sample size during iteration matters.** The user shouldn't pay for 100 records per iteration when they're just tuning phrasing. Default sample is 10 records per iteration; the final TAM query uses the user's `--max-records`. This is made explicit in the cost display.
- **"Locked" visual indicator** — a 🔒 emoji or `[LOCKED]` tag in the Source column of the QueryPlan panel. This is critical UX: the user needs to see at a glance which fields the OLM is allowed to re-derive vs which ones are "mine now."
- **Abort is always exit code 0**, not an error. Aborting is a valid outcome of "I looked at the plan and decided not to run this." Exit code 1/2+ are reserved for actual failures per PRD US-016.

</specifics>

<deferred>
## Deferred Ideas

These came up during analysis but belong in later work:

- **Editing negation filters in the UI** (`--negate-phrase`, `--negate-category`, etc.) — supported as CLI args today, not editable in the v1 loop UI. Add in Phase 3.x or a later enhancement once users tell us they need it.
- **Editing advanced targeting** (`tech_stack`, `variance`, `consensus`, `subdomain`) — same rationale as above. Shown as read-only in the panel's "Raw (advanced)" row.
- **Persisting iteration state across CLI invocations** — e.g., "resume the loop I was running yesterday." Would need SQLite persistence similar to Phase 1's tasks table. Not in scope. If users ask, revisit when we do Phase 4's `tasks` command group.
- **Undo/redo within the loop** — nice-to-have; defer until someone asks for it.
- **Saving a refined query plan as a saved query** (via `/queries` endpoint) — natural extension, but that's `commands/saved.py` territory. Post-loop hook could offer "save this plan?" in a later version.
- **Multi-seed A/B comparison in one loop** — running two query plans side by side. Interesting idea, complex UX, defer.
- **Agent-mode auto-loop** — Claude Code agent iterating without `--confirm` by reading `--json` output, mutating, resubmitting. This is **already enabled** by D-18 (JSON query plan always present), but we could ship a docs page `docs/agent-loop.md` showing the pattern. Document writing deferred to Phase 5 (Discovery Skill), which naturally needs this.
- **LLM-assisted plan refinement** (e.g., "suggest phrases to add based on the sample records") — out of scope; could become an `--enhance` sub-flow later.

</deferred>

---

*Phase: 03-olm-feedback-loop*
*Context gathered: 2026-04-10*
*Mode: --auto (all 10 gray areas resolved with recommended defaults)*
