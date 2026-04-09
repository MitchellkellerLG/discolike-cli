# Phase 1: Async Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 01-async-infrastructure
**Areas discussed:** Task persistence schema, AsyncTaskManager API surface, Signal handling approach, Polling progress display
**Mode:** Auto (--auto flag, recommended defaults selected)

---

## Task Persistence Schema

| Option | Description | Selected |
|--------|-------------|----------|
| Same cache.db | Add tasks table to existing ~/.discolike/cache.db | ✓ |
| Separate tasks.db | New SQLite file for task data | |
| In-memory only | No persistence, tasks lost on exit | |

**User's choice:** [auto] Same cache.db (recommended default)
**Notes:** Existing CacheManager pattern handles SQLite connections. No benefit to a second DB file for operationally similar data.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal schema | task_id, endpoint, status, submitted_at, last_polled_at, params_json, error_message | ✓ |
| Full schema | Include results_json, cost columns, retry_count | |

**User's choice:** [auto] Minimal schema (recommended default)
**Notes:** Results come from API on resume. No need to cache them locally.

---

## AsyncTaskManager API Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone class (composition) | Takes DiscoLikeClient + CacheManager as args | ✓ |
| Mixin on DiscoLikeClient | Add task methods directly to client | |
| Module-level functions | Stateless functions taking client as param | |

**User's choice:** [auto] Standalone class (recommended default)
**Notes:** Composition keeps client.py focused on HTTP. Task lifecycle is a separate concern.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Callback-based poll | on_status callback for Rich display | ✓ |
| Generator-based poll | yield status updates | |
| Return final result only | No progress visibility | |

**User's choice:** [auto] Callback-based poll (recommended default)
**Notes:** Simpler than generators, aligns with existing Rich console.status() usage.

---

## Signal Handling Approach

| Option | Description | Selected |
|--------|-------------|----------|
| try/except KeyboardInterrupt | Wrap poll loop, print task_id on interrupt | ✓ |
| signal.signal(SIGINT) | Global signal handler | |
| atexit handler | Register cleanup on exit | |

**User's choice:** [auto] try/except KeyboardInterrupt (recommended default)
**Notes:** Most Pythonic, no global side effects. Except block prints task_id to stderr and persists state.

---

## Polling Progress Display

| Option | Description | Selected |
|--------|-------------|----------|
| Rich console.status() spinner | Spinner with status text updates | ✓ |
| Rich progress bar | Progress bar (needs known total) | |
| Plain stderr lines | Periodic status lines | |

**User's choice:** [auto] Rich console.status() spinner (recommended default)
**Notes:** Matches existing Rich patterns. Degrades gracefully in non-TTY.

---

## Claude's Discretion

- File organization (tasks.py vs async_tasks.py)
- Internal helper naming
- Test structure
- CacheManager extension vs standalone SQL

## Deferred Ideas

None.
