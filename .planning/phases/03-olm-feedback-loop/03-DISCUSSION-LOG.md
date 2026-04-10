# Phase 3: OLM Feedback Loop - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> CONTEXT.md is the authoritative decisions document.

**Date:** 2026-04-10
**Mode:** `--auto` (all gray areas auto-resolved; no interactive questions)
**Phase:** 03-olm-feedback-loop
**Requirements covered:** LOOP-01 through LOOP-10

---

## Prior Context Loaded

- `.planning/PROJECT.md` — Core value: feedback loop between Claude Code client context and DiscoLike's search model
- `.planning/REQUIREMENTS.md` — 10 LOOP-* requirements mapped to Phase 3
- `.planning/ROADMAP.md` — Phase 3 goal, 6 success criteria
- `.planning/phases/01-async-infrastructure/01-CONTEXT.md` — Phase 1 established: sync httpx, SQLite tasks table, AsyncTaskManager (NOT reused here)
- `.planning/phases/02-async-commands/02-CONTEXT.md` — Phase 2 established: Click patterns, OutputManager reuse, cost footer conventions
- `CLAUDE.md` — Tech stack locked (questionary 2.1.1, Rich, Pydantic v2, no asyncio)
- `../leadgrow-hq/archive/mcp-docs/DiscoLike_API_Reference.md` — `X-Applied-Filters` response header documented at line 226

## Codebase Scout Findings

- `src/discolike/commands/discover.py` (270 lines) — current discover command, `discovery_filters` decorator, `collect_filters()` helper. No existing header-capture logic.
- `src/discolike/client.py:275-304` — `client.discover()` calls `self._request()` then `resp.json()` — **throws away `resp.headers`**. Must be modified.
- No existing `QueryPlan` type or `--confirm` flag anywhere in repo.
- `CostTracker` (`cost.py`) already exposes `record_call`, `estimate`, `last_call`, `session_total` — sufficient for cumulative cost display without new infrastructure.
- 18 command files in `src/discolike/commands/` — this phase only modifies `discover.py` and adds two new top-level modules (`query_loop.py`, `query_state.py`).
- `questionary` NOT yet in `pyproject.toml` — Phase 3 is its first actual use (decision was pre-approved in CLAUDE.md Technology Stack section).

## Gray Areas Identified and Auto-Resolved

All 10 areas were resolved using recommended defaults per `--auto` mode. For each, the alternatives considered and the reason the chosen option wins:

### 1. QueryPlan data model & parsing

**Options considered:**
- A (chosen): Pydantic `QueryPlan` in `types.py`, attached to `DiscoverResult` as new optional field
- B: Return tuple `(DiscoverResult, QueryPlan)` from `client.discover()` — breaks backwards compat
- C: Separate parser module — premature abstraction for 10-20 lines of logic

**Chosen:** A. Additive, backwards-compatible, follows existing Pydantic pattern in `types.py`. Header parsing lives in `client.discover()` (where the response lives) — no cross-module indirection.

### 2. QueryPlan display format

**Options considered:**
- A (chosen): Rich Panel + single Table with section separator rows
- B: Rich Tree — hierarchical but harder to scan at a glance
- C: Plain formatted text — inconsistent with rest of CLI

**Chosen:** A. Matches existing OutputManager style, scales to wide terminals, section separators give hierarchy without nested table complexity.

### 3. Interactive review UX

**Options considered:**
- A (chosen): `questionary.select` main menu → edit sub-menu → field-specific prompt
- B: Single massive form with all fields — overwhelming, breaks questionary's one-prompt-at-a-time model
- C: Command-line editor (`$EDITOR` on a YAML file) — powerful but high-friction

**Chosen:** A. Matches questionary's design grain. Each interaction is one decision. User doesn't drown in options.

### 4. Prevent OLM re-derivation (LOOP-03)

**Options considered:**
- A (chosen): Track `locked_fields` set in QueryState; on resubmit, force `auto_icp_text=false` and `auto_phrase_match=false`
- B: Send every field explicitly on every resubmit — loses info about what was auto-derived vs locked
- C: Server-side locking via a new API param — not documented, not in scope

**Chosen:** A. Respects the actual API contract: the `auto_*` flags exist exactly for this purpose. Minimal client-side state.

### 5. QueryState persistence (LOOP-10)

**Options considered:**
- A (chosen): In-memory only — dataclass, lives for one CLI invocation
- B: SQLite persistence in the `tasks` table from Phase 1 — overloads that table's semantics (it's for async jobs)
- C: New SQLite table for query sessions — second persistence layer, scope creep

**Chosen:** A. Discover is synchronous. There's no "resume a session" use case because sessions are single CLI invocations. Ctrl+C loses the loop; user re-runs. This is fine.

### 6. Cost tracking across iterations (LOOP-06)

**Options considered:**
- A (chosen): Reuse `CostTracker.session_total` + `.estimate()`; read per-iteration cost from `last_call`
- B: New `IterationCostTracker` class — duplicates existing functionality
- C: Calculate cost manually inside `query_loop.py` — bypasses the audit trail

**Chosen:** A. Zero new infrastructure. CostTracker was built for exactly this and the `--dry-run` path already uses `.estimate()` the same way.

### 7. --max-iterations default

**Options considered:**
- A (chosen): Default 3, configurable via `--max-iterations`
- B: Default 5 — too many cheap calls for no benefit
- C: No limit — violates LOOP-07 requirement

**Chosen:** A. Matches requirement (LOOP-07 says default 3). Three iterations is enough for "initial → one refinement → final check" which is the dominant pattern.

### 8. TTY guard (LOOP-09)

**Options considered:**
- A (chosen): `click.UsageError` at command entry with error message pointing to `--json` alternative
- B: Silently downgrade to `--json` mode when no TTY — surprises the user, violates explicit-action principle
- C: Just print a warning and continue — loop will hang waiting for stdin, defeats the purpose of the guard

**Chosen:** A. Fail loudly, fail fast, fail helpfully. The error message tells agents exactly how to participate in the loop without `--confirm`.

### 9. JSON query plan output (LOOP-05)

**Options considered:**
- A (chosen): `--json` always includes `query_plan` for the latest call; when combined with `--confirm`, includes full iteration trace
- B: Separate `--query-plan-json` flag — redundant with existing `--json`
- C: QueryPlan only in a special command like `discover plan` — fragments the API surface

**Chosen:** A. One flag, two modes. Agents can use `--json` without `--confirm` (one-shot call, explicit params, own loop). Automated tests can use `--json` with `--confirm` (full trace). Natural.

### 10. Diff view (LOOP-08)

**Options considered:**
- A (chosen): Rich Table with `Field | Previous | Current` columns, color-coded, auto-displayed iteration 2+
- B: `difflib.unified_diff` output — text-diff semantics don't match structured field changes
- C: Side-by-side full-panel comparison — visually noisy

**Chosen:** A. Structured diff for structured data. Only shows fields that changed. Color coding is lightweight, matches Rich conventions already in use.

## Additional Decisions (not a "gray area" but surfaced during analysis)

### Iteration sample size (D-16)

Iterating over 100-record samples per step would cost 10x what 10-record samples cost. The final TAM query uses the user's `--max-records`; iteration uses a new `--sample-records` flag (default 10). This was not explicit in the requirements but emerged naturally from the cost-awareness principle (LOOP-06). Documented in D-16.

### New files vs modifying existing

`query_loop.py` and `query_state.py` are new top-level modules (not inside `commands/`) because they're not commands themselves — they're library code used by one command. This follows the existing pattern: `client.py`, `cost.py`, `cache.py`, `async_tasks.py` all live at top level.

## Scope Creep Redirected

- **"Editing negation filters in UI"** — belongs in v1.1, documented in Deferred Ideas
- **"Persisting iteration state across CLI invocations"** — would need a new SQLite table, out of scope, deferred
- **"LLM-assisted plan refinement"** — out of scope, mentioned in Deferred Ideas as a future enhancement direction
- **"Agent-mode auto-loop documentation"** — Phase 5's Discovery Skill is the right home for this docs page

## Files That Will Change

**Modified:**
- `src/discolike/commands/discover.py` — 3 new Click options, loop dispatch
- `src/discolike/client.py` — `discover()` captures headers, builds QueryPlan
- `src/discolike/types.py` — new `QueryPlan` model, `DiscoverResult.query_plan` field
- `pyproject.toml` — add `questionary>=2.1,<3.0`

**New:**
- `src/discolike/query_loop.py` — loop orchestration, render functions, questionary prompts
- `src/discolike/query_state.py` — `QueryState`, `IterationRecord`, `FieldDiff` dataclasses
- `tests/test_query_loop.py` — unit tests for loop (mock questionary)
- `tests/test_query_state.py` — unit tests for state + diff
- `tests/test_client_query_plan.py` — unit tests for header parsing (mock respx)

## Requirement Traceability

| Req | Decision(s) |
|-----|-------------|
| LOOP-01 | D-01, D-02, D-03 (QueryPlan model + header parsing) |
| LOOP-02 | D-07, D-08, D-09 (interactive questionary flow) |
| LOOP-03 | D-04, D-06 (locked_fields + auto_* flag forcing) |
| LOOP-04 | D-15 (explicit convergence gate, no silent) |
| LOOP-05 | D-18, D-19 (--json always has query_plan) |
| LOOP-06 | D-12, D-13 (cumulative cost display) |
| LOOP-07 | D-15, D-20 (--max-iterations default 3) |
| LOOP-08 | D-14 (diff view) |
| LOOP-09 | D-17 (TTY guard with UsageError) |
| LOOP-10 | D-04, D-05, D-06 (mutable QueryState, in-memory, merge-not-replace) |

All 10 requirements covered. No gaps.

---

*Log written: 2026-04-10*
