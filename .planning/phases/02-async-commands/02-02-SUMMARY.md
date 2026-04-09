---
phase: "02"
plan: "02"
subsystem: discogen-command
tags: [discogen, async-polling, interim-results, cost-estimate, on_result-callback, personas, tdd]
dependency_graph:
  requires: [async_tasks.py, client.py, domain_input.py, errors.py, output.py, types.py, cache.py, cli.py]
  provides: [commands/discogen.py, DiscoGenResult model, on_result callback in poll(), discogen_personas_submit() in client.py]
  affects: [cli.py (add_command), async_tasks.py (poll signature), client.py (new method), discolike discogen --help]
tech_stack:
  added: []
  patterns: [TDD, click-group-subcommands, async-poll-with-on_result, rich-live-interim, cost-estimate-preflight]
key_files:
  created:
    - src/discolike/commands/discogen.py
    - tests/test_discogen.py
    - tests/fixtures/discogen_interim.json
    - tests/fixtures/discogen_completed.json
  modified:
    - src/discolike/async_tasks.py (on_result param added to poll())
    - src/discolike/types.py (DiscoGenResult model added)
    - src/discolike/client.py (discogen_personas_submit() added)
    - src/discolike/cli.py (discogen command registered)
    - tests/test_async_tasks.py (test_on_result_callback_receives_full_dict added)
decisions:
  - "on_result callback added to poll() with default None -- backward compatible, no existing callers broken"
  - "discogen_personas_submit() added to client.py as minimal extension to existing async pattern"
  - "Rich Live interim table goes to stderr (cli_ctx.output._stderr) keeping stdout clean for --json"
  - "CliRunner(mix_stderr=False) unavailable in Click 8.1 -- tests use result.output only for assertions"
  - "Non-TTY mode uses lambda no-op for on_result to keep poll() interface consistent"
metrics:
  duration_minutes: 35
  completed_date: "2026-04-09"
  tasks_completed: 2
  files_changed: 9
requirements_completed: [GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, GEN-06]
---

# Phase 02 Plan 02: DiscoGen Command Group Summary

**One-liner:** DiscoGen `run` and `personas` Click group with async polling, Rich Live interim display, pre-flight cost estimates, and on_result callback extension to AsyncTaskManager.

## What Was Built

### Task 1: AsyncTaskManager.poll() on_result callback + DiscoGenResult model

Extended `AsyncTaskManager.poll()` with a new `on_result: Callable[[dict, int, float], None] | None = None` parameter. The callback fires after `on_status` on every poll iteration, receiving the full raw API response dict. This lets commands inspect `interim_results` without blocking the poll loop.

Added `DiscoGenResult` Pydantic model to `types.py` (domain, persona_id, result fields with `extra="allow"` for flexible API responses).

Created two test fixtures: `discogen_interim.json` (in_progress + interim_results array) and `discogen_completed.json` (completed + results array).

### Task 2: DiscoGen command group

Created `src/discolike/commands/discogen.py` with:

- **`discogen run`**: Submits domains to `/discogen/process`. Options: `--prompt` (required), `--input`/`--domain`, `--context-mode` (website/profile/domain), `--web-search`, `--yes`. Pre-flight cost estimate table to stderr. Confirmation gate (non-TTY requires `--yes`). Rich Live interim results in TTY mode. Polls with `on_result` callback.
- **`discogen personas`**: Submits persona IDs to `/discogen/process-personas`. Same pipeline but `--context-mode` choices are full/company/profile/name_only and `--persona-id` replaces `--domain`.

Added `discogen_personas_submit()` to `client.py` following the same dry_run + `_post_json` pattern as other async endpoints.

Registered `discogen` group in `cli.py`.

## Test Coverage

16 tests in `tests/test_discogen.py` covering:
- Submit and poll lifecycle (params verified)
- Context mode passthrough (run: website/profile/domain; personas: full/company/profile/name_only)
- Task cache save before poll
- Web search warning on >50 domains
- Pre-flight cost estimate in output
- --yes bypasses confirm
- Non-TTY without --yes exits 2
- Web search param passthrough
- Input file domain reading
- Personas endpoint called (not run endpoint)
- Personas invalid context mode rejected (exit 2)
- Personas web search
- Interim results (on_result kwarg presence)
- on_result kwarg passed to poll()
- JSON output structure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CliRunner result.stderr not available in Click 8.1**
- **Found during:** Task 2, test implementation
- **Issue:** `CliRunner(mix_stderr=False)` not supported in Click 8.1.x installed version. Tests using `result.stderr` raise ValueError.
- **Fix:** Updated all test assertions to use `result.output` only (stderr is mixed into output when not using mix_stderr). Consistent with pattern established in 02-01 and documented in STATE.md decisions.
- **Files modified:** tests/test_discogen.py
- **Commit:** 1417f44

**2. [Rule 3 - Blocking] discogen_personas_submit() missing from client.py**
- **Found during:** Task 2, implementing personas subcommand
- **Issue:** Plan noted this method needed to be added to client.py as part of task 2. Added as minimal extension per existing async submit pattern.
- **Fix:** Added `discogen_personas_submit()` method to client.py after `discogen_submit()`.
- **Files modified:** src/discolike/client.py
- **Commit:** 1417f44

## Out-of-Scope Issues

One pre-existing test failure found: `tests/test_validate.py::TestValidateOptions::test_web_search_warns_for_many_domains` uses `result.stderr` (same Click 8.1 compat issue). This was introduced in plan 02-01 and is out of scope for this plan. Logged to deferred-items.

## Known Stubs

None. Both endpoints wire through to real client methods and return real API response shapes via the fixture pattern.

## Self-Check: PASSED
