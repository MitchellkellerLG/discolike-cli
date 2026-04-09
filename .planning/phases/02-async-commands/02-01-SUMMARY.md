---
phase: "02"
plan: "01"
subsystem: validate-command
tags: [validate, domain-input, icp, async-polling, sort, cost-estimate]
dependency_graph:
  requires: [async_tasks.py, client.py, errors.py, output.py, types.py, cache.py]
  provides: [domain_input.py, commands/validate.py, ValidateResult model]
  affects: [cli.py, discolike validate --help]
tech_stack:
  added: []
  patterns: [TDD, click-command, async-poll, domain-input-sniffing]
key_files:
  created:
    - src/discolike/domain_input.py
    - src/discolike/commands/validate.py
    - tests/test_domain_input.py
    - tests/test_validate.py
    - tests/fixtures/validate_completed.json
  modified:
    - src/discolike/types.py
    - src/discolike/cli.py
decisions:
  - "CliRunner in this Click version does not support mix_stderr= — used default CliRunner() and extract JSON from mixed output via _extract_json() helper"
  - "Pre-flight cost estimate goes to stderr (Rich Console(stderr=True)) — tests parse JSON portion of output via first '{' index split"
  - "Sort no+high last by inverting confidence order for 'no' fit results"
metrics:
  duration_seconds: 275
  completed_date: "2026-04-09"
  tasks_completed: 2
  files_created_or_modified: 7
---

# Phase 02 Plan 01: Validate Command Summary

Domain input helper and `discolike validate` command — ICP validation with triple input mode (file/stdin/inline), pre-flight cost estimate, sorted results (yes+high first, no+high last), and full test coverage.

## What Was Built

### Task 1: Domain input helper + types + test fixtures

`src/discolike/domain_input.py` — shared domain list parsing with three input modes:

- **File input**: `.csv` auto-sniffs for domain/website/url column headers (case-insensitive), falls back to first column. Plain text splits on newlines.
- **Stdin pipe**: detects JSON `{"records": [...]}` or `[{domain}]` format, falls back to newline text.
- **Inline**: `--domain` args passed directly.

`validate_domain_count()` enforces a 10,000 domain cap with a clear error message.

`ValidateResult` Pydantic model added to `types.py` with `domain`, `Fit`, `Confidence`, `Reasoning` fields.

`tests/fixtures/validate_completed.json` with 7 domains covering all fit/confidence combinations for sort order testing.

### Task 2: Validate command + CLI registration

`src/discolike/commands/validate.py` — full ICP validation workflow:

1. Reads domains via `read_domains()` + enforces cap
2. Warns when `--web-search` used on >50 domains
3. Shows pre-flight cost estimate table to stderr
4. Confirmation gate: `--yes` required in non-interactive mode; `click.confirm()` in TTY
5. Submits to `client.validate_icp_submit(params)`
6. Saves task to cache BEFORE poll (Ctrl+C survivable per D-03)
7. Polls via `AsyncTaskManager.poll()`
8. Normalizes dict results `{domain: {Fit, Confidence, Reasoning}}` to list
9. Sorts with compound key: yes > partial > no, high > medium > low (inverse for "no")
10. Renders via `output.render()` with cost footer

`src/discolike/cli.py` — `validate` command registered with `cli.add_command(validate)`.

## Test Results

- `tests/test_domain_input.py`: 20 tests, all passing
- `tests/test_validate.py`: 11 tests, all passing
- Total: 31 new tests, 0 regressions (pre-existing 28 failures from broken `mix_stderr=False` in conftest.py unaffected)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CliRunner mix_stderr not supported in this Click version**
- **Found during:** Task 2, RED phase
- **Issue:** `CliRunner(mix_stderr=False)` raises TypeError — this Click version does not accept that kwarg
- **Fix:** Used `CliRunner()` (default) and created `_extract_json()` helper in test file to parse JSON from mixed stdout output by finding the first `{`
- **Files modified:** `tests/test_validate.py`
- **Commit:** 4139185

## Known Stubs

None — all data is live (mocked in tests but real in production flow). The validate command wires directly to `client.validate_icp_submit` and `AsyncTaskManager`.

## Self-Check: PASSED
