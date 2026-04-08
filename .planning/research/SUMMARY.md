# Research Summary

**Project:** DiscoLike CLI v2 — OLM Feedback Loop & AI Discovery
**Researched:** 2026-04-08
**Confidence:** HIGH

## Executive Summary

Transform the one-shot discovery CLI into a closed-loop query refinement system. The core mechanism: submit discover call → extract `X-Applied-Filters` from response header → present structured query plan → accept adjustments → resubmit with explicit params → repeat until convergence → fire full TAM query. Three async capability clusters layer on top: AI enrichment (DiscoGen), ICP validation, and auto-segmentation — all sharing the same `task_id → poll → results` pattern.

Strictly additive: one new dependency (`questionary>=2.1,<3.0`), two new infrastructure files, five new command files, targeted modifications to existing client/cache/discover. No architectural surgery needed.

## Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Interactive prompts | questionary 2.1.1 | Only maintained option. InquirerPy dead, python-inquirer Unix-only |
| Async polling | stdlib `time.sleep` | Deliberate wait, not retry-on-failure. tenacity/backoff wrong abstraction |
| Progress display | Rich (existing) | `console.status()` + `rich.live.Live` — zero new deps |
| TTY guard | `sys.stdin.isatty()` | questionary crashes on non-TTY. `--confirm` must be gated |

**Critical constraint:** Never wrap questionary calls inside `rich.live.Live` — event loop conflict.

## Table Stakes

- `X-Applied-Filters` extraction + structured query plan display
- `--confirm` flag on `discover` (opt-in, preserves backwards compat)
- Explicit param resubmission after iteration 1 (prevents re-derivation overwriting adjustments)
- Machine-readable query plan output (`--json`) for agent workflows
- Shared `AsyncTaskManager` with SQLite task persistence
- `discolike validate` and `discolike discogen` commands
- Cumulative cost display per iteration + DiscoGen pre-flight estimate

## Architecture

Two new infrastructure components:
1. **AsyncTaskManager** (`async_tasks.py`) — shared poll/progress/cancel lifecycle; SQLite task persistence; Ctrl+C handling
2. **QueryPlan + QueryPlanPresenter** (`query_plan.py`) — OLM loop data model; bridges `X-Applied-Filters` into reviewable plan; TTY-aware (interactive vs JSON)

New Pydantic model: `DiscoverResponse` wrapping existing `DiscoverResult` + `applied_filters` dict from response headers.

Five new command files: `discogen.py`, `validate.py`, `segment.py`, `llm_providers.py`, `search_providers.py`.

## Critical Pitfalls

1. **Quota burn** — Each feedback iteration = $0.18 + records. Need `--max-iterations` (default 3) and per-iteration cost display
2. **DiscoGen dual cost** — DiscoLike credits + LLM fees stack independently. CostTracker only models DiscoLike side. Pre-flight estimate must show both
3. **Task ID loss on exit** — Async jobs run server-side after Ctrl+C. Persist task_id to SQLite before first poll
4. **X-Applied-Filters parsing** — Current `discover()` discards response headers entirely. Defensive parsing needed
5. **State loss between iterations** — Mutable `QueryState` with merge-not-replace across iterations

## Recommended Phases (5)

| Phase | Name | Delivers | Dependencies |
|-------|------|----------|-------------|
| 1 | Async Infrastructure | AsyncTaskManager, SQLite tasks table, client submit/status/cancel methods, new types | None |
| 2 | Async Commands | `validate`, `discogen` with async progress, pre-flight cost estimates | Phase 1 |
| 3 | OLM Feedback Loop | `--confirm` flag, query plan display, mutable QueryState, convergence gate, cost gates | Phase 1 (client changes) |
| 4 | Segment + BYOM Config | `segment` (Pro+ gated), `llm-providers`, `search-providers` CRUD | Phase 1 |
| 5 | Discovery Skill | Multi-dimensional discovery skill in lg-research/skills/ | Phases 2-4 |

**Research flags:** Phases 1, 2, 4 follow standard patterns (skip research during planning). Phase 3 needs UX design review (questionary + Rich interleaving). Phase 5 needs judgment design work (seed analysis prompting, dimension weighting).

---
*Ready for roadmap: yes*
