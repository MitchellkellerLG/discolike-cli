# Phase 2: Async Commands - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 02-async-commands
**Areas discussed:** Input handling, Results display, Cost estimate UX, Command structure
**Mode:** Auto (all areas auto-selected, recommended defaults chosen)

---

## Input Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Triple input (--input, stdin, --domain) | File, pipe, and inline args — matches discover pattern | ✓ |
| File-only (--input required) | Simpler but breaks pipe integration | |
| Stdin-only (no file flag) | Forces pipe even for file input | |

**User's choice:** [auto] Triple input — recommended default matching existing discover pattern and VAL-03 pipe requirement
**Notes:** stdin detection via sys.stdin.isatty(). CSV auto-detect domain column. Client-side 10k cap.

---

## Results Display

| Option | Description | Selected |
|--------|-------------|----------|
| Sorted table (fit+confidence groups) | yes+high first, no+high last — best matches at top | ✓ |
| Flat table (API order) | No sorting, raw order from API | |
| Grouped sections (fit=yes / fit=partial / fit=no) | Visual separation but more complex | |

**User's choice:** [auto] Sorted table with fit+confidence grouping — recommended default matching VAL-02 spec

| Option | Description | Selected |
|--------|-------------|----------|
| Rich live table for interim results | Appends rows as interim_results grow during polling | ✓ |
| Progress bar only | Show percentage, final table at end | |
| Periodic stderr updates | Print "X/Y complete" lines | |

**User's choice:** [auto] Rich live table for interim results — recommended default using existing Rich patterns (GEN-06)
**Notes:** Output format parity (--json/--csv/table) with existing commands.

---

## Cost Estimate UX

| Option | Description | Selected |
|--------|-------------|----------|
| Display + confirm gate (y/N) | Show cost table, require explicit confirm, --yes bypasses | ✓ |
| Display only (auto-proceed) | Show cost, continue automatically | |
| No pre-flight (cost in footer after) | Only show cost after completion | |

**User's choice:** [auto] Display + confirm gate — recommended default since LLM operations cost real money (GEN-03)
**Notes:** Estimate from domain_count x context_mode rate. Range display (min-max).

---

## Command Structure

| Option | Description | Selected |
|--------|-------------|----------|
| validate as standalone, discogen as group | validate = single command, discogen run + discogen personas | ✓ |
| Both as groups | Overengineered for validate's single purpose | |
| Both as flat commands | discogen-personas is awkward as flat | |

**User's choice:** [auto] validate standalone + discogen group — recommended default for clean namespace
**Notes:** --context-mode with click.Choice per subcommand. --web-search with >50 domain warning.

---

## Claude's Discretion

- Internal helper functions for domain list parsing
- Rich table column widths and truncation
- Test fixture structure
- Whether to share input parsing or duplicate

## Deferred Ideas

None — discussion stayed within phase scope.
