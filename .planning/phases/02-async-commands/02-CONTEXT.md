# Phase 2: Async Commands - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Two new CLI command groups — `validate` and `discogen` — that wrap Phase 1 async infrastructure into user-facing commands. Users can validate domain lists against ICP descriptions and run AI-powered enrichment prompts against domains or contact personas. Includes input handling (file, stdin pipe, inline), output formatting (sorted tables, interim results), pre-flight cost estimates, and context mode selection. No OLM feedback loop (Phase 3), no segment (Phase 4), no provider config (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Input Handling
- **D-01:** Triple input pattern: `--input FILE` for CSV/text files, stdin pipe detection via `sys.stdin.isatty()`, and `--domain` inline args for small lists. If not TTY and no `--input`, read stdin. This enables `discolike discover ... | discolike validate --icp "description"` (VAL-03).
- **D-02:** File format: CSV with auto-detect domain column (looks for "domain", "website", "url" headers, falls back to first column) + plain text (one domain per line). Sniff format from extension or content.
- **D-03:** Client-side domain count cap at 10,000 matching API limit. Error before submission with clear message showing count vs limit.

### Results Display
- **D-04:** Validate results sorted: yes+high first, then yes+medium, yes+low, partial (by confidence), no+low, no+medium, no+high last. Confidence groups within fit level. This puts best matches at top and clear non-matches at bottom (VAL-02).
- **D-05:** DiscoGen interim results displayed via Rich live table that appends rows as `interim_results` grow during polling. Poll response includes `interim_results` array — diff against previous poll to show new rows. Falls back to progress percentage when not TTY.
- **D-06:** Output format parity with existing commands: `--json`, `--csv`, and Rich table modes. Same `OutputManager` pattern. Cost shown in table footer (table mode) or `_meta.cost` (JSON mode).

### Cost Estimate UX
- **D-07:** Pre-flight cost display for discogen: show estimated DiscoLike credits + LLM fees as a Rich table before submission, then prompt `Proceed? [y/N]` confirm gate. `--yes` flag bypasses confirm for scripts/automation. Validate command also shows estimate but lower stakes (no LLM fees on basic mode).
- **D-08:** Cost estimation calculated from: domain count x context_mode rate. Display as estimate range (min-max) since exact cost depends on actual content length. Rates from API docs: `website` = credits + model fees, `profile` = credits + model fees, `domain` = model fees only.

### Command Structure
- **D-09:** `validate` is a standalone command: `discolike validate --icp "description" --input domains.csv`. No subcommands needed — single purpose.
- **D-10:** `discogen` is a Click group with subcommands: `discolike discogen run --prompt "..." --input domains.csv` and `discolike discogen personas --prompt "..." --input contacts.csv`. Clean namespace, extensible.
- **D-11:** Context mode surfaces as `--context-mode` flag with `click.Choice`. Validate and discogen-run share `website|profile|domain`. Discogen-personas uses `full|company|profile|name_only`. Default: `website` for domains, `profile` for personas (matching API defaults).
- **D-12:** `--web-search` boolean flag on both discogen subcommands. When domain count > 50, print warning to stderr: "Web search on {N} domains — this will significantly increase cost. Use --yes to skip this warning." Still proceeds unless user Ctrl+C's.

### Async Integration
- **D-13:** Both commands use AsyncTaskManager.poll() with Rich console.status() spinner for progress. Validate shows "Validating {N} domains..." during poll. DiscoGen shows "Processing {N} domains..." with interim result count when available.
- **D-14:** Submit methods from Phase 1 client used directly. Command layer: parse CLI args → build params dict → client.submit() → cache.save_task() → task_manager.poll() → format output. Standard pipeline.
- **D-15:** Ctrl+C during poll handled by AsyncTaskManager (Phase 1 D-09/D-10) — no additional signal handling needed in commands.

### Claude's Discretion
- Internal helper functions for domain list parsing (shared between validate and discogen)
- Rich table column widths and truncation for results display
- Test fixture structure for validate and discogen responses
- Whether to share a `DomainInputMixin` or just duplicate the 10 lines of input parsing

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### API Reference
- `leadgrow-hq/archive/mcp-docs/DiscoLike_API_Reference.md` lines 1102-1230 — DiscoGen endpoints (process, process-personas, models, status, cancel), parameter tables, context modes, response flow
- `leadgrow-hq/archive/mcp-docs/DiscoLike_API_Reference.md` lines 1168-1230 — Validate ICP endpoint, parameters, response flow with Fit/Confidence/Reasoning columns
- `reference/discolike-field-reference.md` — Field reference for response shapes
- `reference/discolike-workflow.md` — Workflow patterns

### Phase 1 Foundation (already built)
- `src/discolike/async_tasks.py` — AsyncTaskManager with poll/cancel/resume, backoff, Ctrl+C handling
- `src/discolike/client.py` lines 441-480 — discogen_submit, validate_icp_submit, segment_submit, task_status, task_cancel
- `src/discolike/cache.py` — CacheManager with tasks table (save_task, update_task_status, get_task, list_tasks)
- `src/discolike/types.py` — TaskSubmitResponse, TaskStatusResponse Pydantic models
- `src/discolike/errors.py` — TaskError, TaskTimeoutError hierarchy

### Existing Patterns to Follow
- `src/discolike/commands/discover.py` — Discovery filters pattern, Click command structure, shared decorators
- `src/discolike/output.py` — OutputManager for table/JSON/CSV rendering, cost footer pattern
- `src/discolike/commands/enrich.py` — Example of a command that processes domain lists (if exists)
- `src/discolike/cli.py` — Main CLI group, _get_context helper, get_client helper

### Project Docs
- `CLAUDE.md` — Architecture overview, tech stack (questionary, no asyncio), dev commands
- `PRD.md` — Full product requirements with user stories
- `.planning/phases/01-async-infrastructure/01-CONTEXT.md` — Phase 1 decisions (D-01 through D-12) that this phase builds on

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AsyncTaskManager` (`async_tasks.py`): Full poll/cancel/resume lifecycle — commands just call submit + poll
- `OutputManager` (`output.py`): Table/JSON/CSV rendering with cost footer — extend for validate/discogen result shapes
- `CostTracker` (`cost.py`): Per-call cost tracking — wire into submit calls
- `discovery_filters` decorator (`commands/discover.py`): Pattern for shared Click options — reuse approach for shared input options
- `handle_errors` decorator (`errors.py`): Error handling wrapper for commands

### Established Patterns
- One file per command group in `src/discolike/commands/`
- Click group at `cli.py`, commands registered via `@cli.group()` or `@cli.command()`
- `_get_context()` and `get_client()` helpers for shared state
- stderr for progress (console.status), stdout for data (tables/JSON)
- `--json` and `--csv` flags on every data-returning command

### Integration Points
- `src/discolike/cli.py` — Register `validate` command and `discogen` group
- `src/discolike/commands/` — New files: `validate.py`, `discogen.py`
- `src/discolike/types.py` — New Pydantic models for validate results (ValidateResult) and discogen results (DiscoGenResult)
- `src/discolike/output.py` — May need new render methods or the existing `render()` handles dicts fine

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

*Phase: 02-async-commands*
*Context gathered: 2026-04-09*
