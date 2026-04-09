# Phase 2: Async Commands - Research

**Researched:** 2026-04-09
**Domain:** Click CLI commands, Rich live display, stdin pipe handling, async task polling, CSV/file input parsing
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Triple input pattern: `--input FILE`, stdin pipe via `sys.stdin.isatty()`, and `--domain` inline args. If not TTY and no `--input`, read stdin. Enables `discolike discover ... | discolike validate --icp "description"`.

**D-02:** File format: CSV with auto-detect domain column (looks for "domain", "website", "url" headers, falls back to first column) + plain text (one domain per line). Sniff format from extension or content.

**D-03:** Client-side domain count cap at 10,000 matching API limit. Error before submission with clear message.

**D-04:** Validate results sort order: yes+high → yes+medium → yes+low → partial (by confidence) → no+low → no+medium → no+high. Best matches at top.

**D-05:** DiscoGen interim results via Rich live table that appends rows as `interim_results` grow. Diff against previous poll to show new rows. Falls back to progress % when not TTY.

**D-06:** Output format parity: `--json`, `--csv`, Rich table modes. Same `OutputManager` pattern. Cost in table footer (table mode) or `_meta.cost` (JSON mode).

**D-07:** Pre-flight cost display for discogen: Rich table showing estimates, then `Proceed? [y/N]` confirm gate. `--yes` flag bypasses. Validate also shows estimate (lower stakes).

**D-08:** Cost estimation: domain_count x context_mode rate. Range display (min-max). `website` = credits + model fees; `profile` = credits + model fees; `domain` = model fees only.

**D-09:** `validate` is a standalone command. No subcommands needed.

**D-10:** `discogen` is a Click group with subcommands: `discogen run` and `discogen personas`.

**D-11:** `--context-mode` flag with `click.Choice`. validate and discogen-run: `website|profile|domain`. discogen-personas: `full|company|profile|name_only`. Defaults: `website` for domains, `profile` for personas.

**D-12:** `--web-search` boolean flag. When domain count > 50, print warning to stderr. Still proceeds unless user Ctrl+C.

**D-13:** Both commands use `AsyncTaskManager.poll()` with `console.status()` spinner. Validate: "Validating {N} domains...". DiscoGen: "Processing {N} domains..." with interim count.

**D-14:** Command pipeline: parse CLI args → build params dict → client.submit() → cache.save_task() → task_manager.poll() → format output.

**D-15:** Ctrl+C during poll handled by AsyncTaskManager — no additional signal handling in commands.

### Claude's Discretion

- Internal helper functions for domain list parsing (shared between validate and discogen)
- Rich table column widths and truncation for results display
- Test fixture structure for validate and discogen responses
- Whether to share a `DomainInputMixin` or just duplicate the 10 lines of input parsing

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. No OLM feedback loop (Phase 3), no segment (Phase 4), no provider config (Phase 4).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VAL-01 | `discolike validate` command accepts ICP text + domain list, submits to `/validate/icp`, polls for results | D-09, D-13, D-14 + API response shape confirmed in API ref lines 1168-1230 |
| VAL-02 | Results sorted: yes+high at top, no+high as exclusion candidates | D-04 + sort key function pattern below |
| VAL-03 | Pipe integration — accepts domain list from stdin or `--input` file | D-01, D-02 + `sys.stdin.isatty()` pattern verified |
| VAL-04 | Context mode selection with cost implications displayed | D-07, D-08, D-11 + API docs confirm 3 modes for validate |
| GEN-01 | `discolike discogen` command with interim display for domain processing | D-10, D-05, D-13 + API interim_results field confirmed |
| GEN-02 | `discolike discogen personas` for contact persona IDs | D-10, D-11 + API docs confirm process-personas endpoint |
| GEN-03 | Pre-flight cost estimate before submission | D-07, D-08 + CostTracker.estimate() available |
| GEN-04 | Context mode selection for domains and personas | D-11 + API docs confirm different mode sets per endpoint |
| GEN-05 | `--web-search` flag with cost warning >50 domains | D-12 + API docs confirm web_search parameter |
| GEN-06 | Interim results display during long-running jobs | D-05 + API status response includes `interim_results` array |
</phase_requirements>

---

## Summary

Phase 2 builds two new command groups — `validate` and `discogen` — on top of the Phase 1 async infrastructure that is already fully built and tested. The implementation is primarily a command layer concern: input parsing, API call orchestration, and output formatting. The hard parts (polling lifecycle, cache persistence, Ctrl+C handling, client HTTP methods) are already done.

The key technical challenge is the Rich live table for interim DiscoGen results. `rich.live.Live` must not run during TTY-interactive questionary calls (per existing CLAUDE.md warning), but Phase 2 has no questionary usage — only passive polling display — so there is no conflict here. The second challenge is stdin pipe detection for `discolike discover ... | discolike validate`, which is solved cleanly with `sys.stdin.isatty()`.

The validate results sort order requires a compound sort key mapping `(fit, confidence)` tuples to integers. The confirmed API response shape for validate is a dict keyed by domain (not a list), requiring normalization before sorting and display.

**Primary recommendation:** Build `domain_input.py` as a shared input helper (not a mixin), `validate.py` as a standalone command, `discogen.py` as a Click group. Three new Pydantic models in `types.py`. Extend `OutputManager` only if needed — the existing `render()` handles dicts and lists of dicts cleanly.

---

## Standard Stack

### Core (already installed — do not revisit)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Click | 8.1.x | CLI framework — commands, groups, options | Locked in pyproject.toml |
| Rich | 13.x | Tables, progress, `console.status()`, `Live` | Already used for all output |
| Pydantic v2 | 2.x | API response models | Locked in pyproject.toml |
| httpx | 0.27+ | HTTP (sync) — already wrapping in client.py | Locked in pyproject.toml |

### Already Built (Phase 1 outputs — consume directly)
| Asset | Location | What It Provides |
|-------|----------|-----------------|
| `AsyncTaskManager` | `src/discolike/async_tasks.py` | `poll()`, `cancel()`, `resume()` with backoff and Ctrl+C |
| Submit methods | `src/discolike/client.py:441-474` | `discogen_submit()`, `validate_icp_submit()`, `segment_submit()` |
| `CacheManager` | `src/discolike/cache.py` | `save_task()`, `update_task_status()`, task persistence |
| `OutputManager` | `src/discolike/output.py` | `render()`, `warning()`, `status()` — handles dict/list/Pydantic |
| `CostTracker` | `src/discolike/cost.py` | `estimate()` for pre-flight, `record_call()` for actuals |
| `handle_errors` | `src/discolike/errors.py:86` | Catches DiscoLikeError, exits with correct code |
| `TaskSubmitResponse` | `src/discolike/types.py:195` | Pydantic model for submit response (`task_id`, `status`) |
| `TaskStatusResponse` | `src/discolike/types.py:203` | Pydantic model for poll response including `interim_results` |

### Testing Stack
| Library | Version | Role |
|---------|---------|------|
| pytest | 8.0+ | Test runner (`testpaths = ["tests"]` in pyproject.toml) |
| respx | 0.21+ | Mock httpx at the transport level |
| click.testing.CliRunner | Click built-in | CLI invocation in tests |

---

## Architecture Patterns

### Recommended Project Structure for Phase 2
```
src/discolike/
├── commands/
│   ├── validate.py         # NEW — standalone validate command
│   └── discogen.py         # NEW — discogen group with run + personas subcommands
├── domain_input.py         # NEW — shared input parsing helper
└── types.py                # EXTEND — add ValidateResult, DiscoGenResult, CostEstimate models

tests/
├── fixtures/
│   ├── validate_completed.json    # Wave 0 gap
│   ├── discogen_interim.json      # Wave 0 gap
│   └── discogen_completed.json    # Wave 0 gap
├── test_validate.py               # Wave 0 gap
├── test_discogen.py               # Wave 0 gap
└── test_domain_input.py           # Wave 0 gap
```

### Pattern 1: Click Group with Subcommands (discogen)
```python
# src/discolike/commands/discogen.py
import click
from discolike.cli import _get_context, get_client
from discolike.errors import handle_errors

@click.group("discogen")
def discogen() -> None:
    """AI-powered domain and persona enrichment."""

@discogen.command("run")
@click.option("--prompt", required=True, help="Prompt to run against each domain")
@click.option("--input", "input_file", type=click.Path(), default=None)
@click.option("--domain", "-d", multiple=True)
@click.option("--context-mode", type=click.Choice(["website", "profile", "domain"]), default="website")
@click.option("--web-search", is_flag=True, default=False)
@click.option("--yes", "auto_confirm", is_flag=True, default=False)
@handle_errors
@click.pass_context
def discogen_run(ctx, prompt, input_file, domain, context_mode, web_search, auto_confirm):
    ...

@discogen.command("personas")
@click.option("--prompt", required=True)
@click.option("--input", "input_file", type=click.Path(), default=None)
@click.option("--context-mode", type=click.Choice(["full", "company", "profile", "name_only"]), default="profile")
@click.option("--web-search", is_flag=True, default=False)
@click.option("--yes", "auto_confirm", is_flag=True, default=False)
@handle_errors
@click.pass_context
def discogen_personas(ctx, prompt, input_file, context_mode, web_search, auto_confirm):
    ...
```
Register in `cli.py`: `cli.add_command(discogen)`

### Pattern 2: Standalone Validate Command
```python
# src/discolike/commands/validate.py
@click.command("validate")
@click.option("--icp", "icp_text", required=True, help="ICP description")
@click.option("--input", "input_file", type=click.Path(), default=None)
@click.option("--domain", "-d", multiple=True)
@click.option("--context-mode", type=click.Choice(["website", "profile", "domain"]), default="website")
@click.option("--web-search", is_flag=True, default=False)
@click.option("--yes", "auto_confirm", is_flag=True, default=False)
@handle_errors
@click.pass_context
def validate(ctx, icp_text, input_file, domain, context_mode, web_search, auto_confirm):
    ...
```

### Pattern 3: Domain Input Helper (shared by validate and discogen)
```python
# src/discolike/domain_input.py
import csv
import sys
from pathlib import Path

MAX_DOMAINS = 10_000

def read_domains(
    input_file: str | None,
    inline_domains: tuple[str, ...],
) -> list[str]:
    """Read domains from file, stdin pipe, or inline args. D-01/D-02/D-03."""
    if input_file:
        return _read_file(Path(input_file))
    if not sys.stdin.isatty():
        return _read_stdin()
    if inline_domains:
        return list(inline_domains)
    raise click.UsageError("Provide --input FILE, pipe domains via stdin, or use --domain.")

def _read_file(path: Path) -> list[str]:
    if path.suffix.lower() == ".csv":
        return _parse_csv(path)
    return _parse_text(path)

def _parse_csv(path: Path) -> list[str]:
    """Auto-detect domain column: 'domain', 'website', 'url', else first column."""
    with path.open() as f:
        reader = csv.DictReader(f)
        headers = [h.lower() for h in (reader.fieldnames or [])]
        col = next((h for h in ["domain", "website", "url"] if h in headers), None)
        if col is None and reader.fieldnames:
            col = reader.fieldnames[0]
        return [row[col] for row in reader if row.get(col)]

def _parse_text(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]

def _read_stdin() -> list[str]:
    """Read newline-separated domains from stdin pipe."""
    return [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

def validate_domain_count(domains: list[str]) -> None:
    """Raise ValidationError if over API limit."""
    if len(domains) > MAX_DOMAINS:
        raise ValidationError(
            f"Domain count {len(domains):,} exceeds API limit of {MAX_DOMAINS:,}. "
            "Reduce your input list."
        )
```

### Pattern 4: Validate Results Sort Key
The API returns results as a dict keyed by domain, not a list. Flatten to list of dicts, then sort.

```python
# Sort order from D-04
_FIT_ORDER = {"yes": 0, "partial": 1, "no": 2}
_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}

def sort_validate_results(results: dict) -> list[dict]:
    """Flatten dict-keyed results and sort: yes+high first, no+high last."""
    rows = [{"domain": domain, **vals} for domain, vals in results.items()]
    
    def sort_key(row):
        fit = row.get("Fit", "no").lower()
        conf = row.get("Confidence", "low").lower()
        # For "no" fit: reverse confidence (no+high = worst = last)
        if fit == "no":
            conf_rank = {"high": 2, "medium": 1, "low": 0}[conf]
        else:
            conf_rank = _CONF_ORDER.get(conf, 1)
        return (_FIT_ORDER.get(fit, 2), conf_rank)
    
    return sorted(rows, key=sort_key)
```

### Pattern 5: DiscoGen Interim Results Live Display
```python
# During poll — diff interim_results between polls
from rich.live import Live
from rich.table import Table

def _poll_with_live(task_manager, task_id, n_domains, console):
    """Poll with live table for interim results. Falls back in non-TTY."""
    if not sys.stdout.isatty():
        # Non-TTY: simple progress percentage
        def on_status(status, attempt, elapsed):
            # Do nothing — data goes to stdout when complete
            pass
        return task_manager.poll(task_id, on_status=on_status)
    
    seen_count = 0
    table = Table(title=f"Processing {n_domains} domains")
    table.add_column("Domain")
    table.add_column("Result")
    
    with Live(table, console=Console(stderr=True), refresh_per_second=2):
        def on_status(status, attempt, elapsed):
            nonlocal seen_count
            # Retrieve current poll result (need to expose it from poll)
            # Note: interim_results come from poll result, not on_status callback
            pass
        return task_manager.poll(task_id)
```

**Note on interim results:** The `on_status` callback in `AsyncTaskManager.poll()` receives `(status, attempt, elapsed)` — it does NOT receive the full poll response dict. To diff interim results, the command must manage its own polling loop OR `AsyncTaskManager.poll()` needs an `on_result` callback that receives the full dict. See **Pitfall 1** below.

### Pattern 6: Pre-flight Cost Estimate Table
```python
def show_cost_estimate(n_domains: int, context_mode: str, web_search: bool, console: Console) -> None:
    """Display estimate range before submission."""
    table = Table(title="Estimated Cost")
    table.add_column("Item")
    table.add_column("Amount")
    table.add_row("Domains", str(n_domains))
    table.add_row("Context mode", context_mode)
    table.add_row("Web search", "Yes" if web_search else "No")
    # Rates are estimates — show range since actual depends on content length
    table.add_row("Estimated cost", "~$X.XX - $Y.YY")
    console.print(table)
```

### Anti-Patterns to Avoid
- **Never use `rich.live.Live` on stdout when output mode is JSON/CSV** — breaks parseable output. Guard with `if cli_ctx.output.is_tty`.
- **Never mix stderr progress with stdout data** — existing OutputManager already enforces this. Interim Live display uses `Console(stderr=True)`.
- **Don't call `click.confirm()` inside a `rich.live.Live` context** — from CLAUDE.md: event loop conflict. Phase 2 confirm gate happens BEFORE polling, so no conflict.
- **Don't build custom stdin detection** — `sys.stdin.isatty()` is the correct stdlib check. Don't use `click.get_text_stream()` for this.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Polling lifecycle | Custom while-loop per command | `AsyncTaskManager.poll()` | Already built in Phase 1 with backoff, timeout, Ctrl+C |
| Output rendering | Custom table per command | `OutputManager.render()` | Handles dict, list, Pydantic — all three output modes |
| JSON/CSV output modes | if/else per command | `OutputManager` | Consistent `--json`/`--csv` flags already wired |
| Error handling | try/except per command | `@handle_errors` decorator | Correct exit codes, JSON error mode |
| Cost display | Custom footer | `OutputManager._render_cost_footer()` | Already outputs to stderr with session total |
| Task persistence | Direct SQLite calls | `CacheManager.save_task()` | D-03: must be saved BEFORE first poll |
| HTTP client | Requests/urllib | Existing `DiscoLikeClient` methods | `discogen_submit()` and `validate_icp_submit()` ready |

**Key insight:** Phase 2 is ~95% plumbing, not logic. Every piece of infrastructure is already built. The only genuinely new code is input parsing, sort logic, interim display diffing, and the command skeletons themselves.

---

## Common Pitfalls

### Pitfall 1: `on_status` Callback Cannot See Interim Results
**What goes wrong:** Developer tries to use `AsyncTaskManager.poll()`'s `on_status` callback to render interim results, but `on_status(status, attempt, elapsed)` doesn't receive the poll response dict — only status string and timing.

**Why it happens:** `AsyncTaskManager.poll()` was designed for status display, not result streaming. The `interim_results` field lives in the raw API response that `poll()` returns at completion, but intermediate poll responses are not surfaced to callers.

**How to avoid:** Two valid approaches:
1. **Extend `poll()`** with an optional `on_result: Callable[[dict], None]` callback that receives the full status dict on each iteration. Call it before the sleep. This is the cleaner approach.
2. **Custom polling loop in the command** — bypass `AsyncTaskManager.poll()` and call `client.task_status()` directly in a loop. Duplicates backoff/timeout logic.

**Recommendation:** Option 1 — add `on_result` to `AsyncTaskManager.poll()` in this phase. The Phase 1 interface doc says `on_status` is `Callable[[str, int, float], None]`. A new `on_result: Callable[[dict, int, float], None] | None = None` alongside it avoids breaking changes.

### Pitfall 2: Validate API Returns Dict-Keyed Results, Not a List
**What goes wrong:** Code assumes `results` from validate is a list of dicts like discover. It's actually `{"domain.com": {"Fit": "yes", "Confidence": "high", "Reasoning": "..."}, ...}`.

**Why it happens:** API reference lines 1202-1210 show the completed response structure clearly — dict keyed by domain, not array. Easy to miss when treating it like other endpoints.

**How to avoid:** Normalize immediately after receiving the result: `[{"domain": k, **v} for k, v in result["results"].items()]`. Do this in a dedicated `_normalize_validate_results()` function.

### Pitfall 3: stdin Pipe Buffering When Piping from `discover`
**What goes wrong:** `discolike discover ... | discolike validate` fails because `discover` outputs a Rich table (not bare domains) when connected to a pipe. The validate command reads Rich markup as domain names.

**Why it happens:** `OutputManager.render()` checks `sys.stdout.isatty()` — when stdout is a pipe (not TTY), it falls into `_render_json()`, which outputs JSON with a `records` array. This is parseable but requires discover to output CSV or JSON domains, not a Rich table.

**How to avoid:** The pipe path (`--csv` on discover, then parse CSV in validate) is the clean approach. But even simpler: when reading stdin, check if the content looks like JSON (starts with `{` or `[`) and extract the domain field automatically. This handles `discolike discover --csv | discolike validate` and also the raw newline case. Document in help text that for piping, use `discolike discover --csv --fields domain | discolike validate`.

**Actually**: `OutputManager.render()` already handles non-TTY stdout by emitting JSON (not Rich table). So `discolike discover | discolike validate` will receive JSON lines. The domain input reader should handle JSON input as a third format: detect `{` as first char and parse as JSON records extracting domain field.

### Pitfall 4: Pre-flight Confirm Gate + `--yes` in Non-TTY Contexts
**What goes wrong:** Script/agent calling discogen without `--yes` hangs waiting for user input.

**Why it happens:** `click.confirm()` blocks on stdin when not TTY. If output is piped, the process hangs forever.

**How to avoid:** Check `sys.stdin.isatty()` before calling `click.confirm()`. If stdin is not a TTY and `--yes` was not passed, raise `click.UsageError("--yes flag required in non-interactive mode")`. This is already the pattern used for questionary in CLAUDE.md Phase 3 notes.

### Pitfall 5: Rich Live + stderr vs stdout Console Conflict
**What goes wrong:** `rich.live.Live` renders on the wrong stream, corrupting JSON output or interleaving with data.

**Why it happens:** If `Live` is initialized with the default `Console()` (stdout), it corrupts `--json` output.

**How to avoid:** Always init Live with `Console(stderr=True)`: `Live(table, console=Console(stderr=True))`. The existing `OutputManager._stderr` can be used directly.

### Pitfall 6: Discogen Results Shape Differs Between Run and Personas
**What goes wrong:** Same result rendering code used for both `discogen run` and `discogen personas`, but field names differ.

**Why it happens:** API reference shows results structure varies by endpoint. `process` results are domain-keyed, `process-personas` are persona_id-keyed.

**How to avoid:** Separate normalization functions for each. `_normalize_discogen_results()` and `_normalize_personas_results()`. Don't abstract prematurely.

---

## Code Examples

### Confirmed API Response Shapes (from API reference — HIGH confidence)

**Validate ICP Completed Response:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "results": {
    "gusto.com": {"Fit": "yes", "Confidence": "high", "Reasoning": "HR and payroll platform for SMBs"},
    "stripe.com": {"Fit": "no", "Confidence": "high", "Reasoning": "Payment processing, not HR/payroll"}
  }
}
```

**DiscoGen Status During Polling:**
```json
{
  "status": "in_progress",
  "progress": 45,
  "interim_results": [...],
  "estimated_cost": 1.23
}
```

**DiscoGen Completed:**
```json
{
  "status": "completed",
  "progress": 100,
  "results": [...],
  "estimated_cost": 2.45,
  "response_format": "..."
}
```

**DiscoGen Initial Submit Response:**
```json
{
  "task_id": "uuid",
  "column_name": [...],
  "status": "in_progress",
  "total_domains": 42
}
```

### Full Command Pipeline (D-14 pattern)
```python
@click.pass_context
def validate(ctx, icp_text, input_file, domain, context_mode, web_search, auto_confirm):
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    
    # 1. Parse input
    domains = read_domains(input_file, domain)
    validate_domain_count(domains)
    
    # 2. Web search warning
    if web_search and len(domains) > 50:
        cli_ctx.output.warning(
            f"Web search on {len(domains)} domains — this will significantly increase cost."
        )
    
    # 3. Pre-flight estimate
    estimate = cli_ctx.cost_tracker.estimate("validate/icp", len(domains))
    # show estimate table...
    if not auto_confirm and sys.stdin.isatty():
        if not click.confirm("Proceed?", default=False):
            raise SystemExit(0)
    elif not auto_confirm and not sys.stdin.isatty():
        raise click.UsageError("--yes flag required in non-interactive mode")
    
    # 4. Submit
    params = {"icp_text": icp_text, "domains": domains, "context_mode": context_mode}
    if web_search:
        params["web_search"] = True
    submit_resp = client.validate_icp_submit(params)
    task_id = submit_resp["task_id"]
    
    # 5. Save task BEFORE poll (D-03, INFRA-02)
    import json
    cli_ctx.cache.save_task(task_id, "validate/icp", json.dumps(params))
    
    # 6. Poll with spinner
    task_mgr = AsyncTaskManager(client, cli_ctx.cache)
    with cli_ctx.output._stderr.status(f"Validating {len(domains)} domains..."):
        result = task_mgr.poll(task_id)
    
    # 7. Normalize + sort
    raw = result.get("results", {})
    rows = sort_validate_results(raw)
    
    # 8. Render
    cli_ctx.output.render(rows, title="ICP Validation Results", cost=client.cost_tracker.last_call)
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` → `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_validate.py tests/test_discogen.py tests/test_domain_input.py -v` |
| Full suite command | `pytest tests/ -v --cov=discolike` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VAL-01 | validate submits to /validate/icp and polls for results | unit | `pytest tests/test_validate.py::test_validate_submits_and_polls -x` | Wave 0 |
| VAL-02 | Results sorted yes+high first, no+high last | unit | `pytest tests/test_validate.py::test_sort_order -x` | Wave 0 |
| VAL-03 | Accepts stdin pipe + --input file + --domain inline | unit | `pytest tests/test_domain_input.py -x` | Wave 0 |
| VAL-04 | --context-mode choices work, cost estimate displayed | unit | `pytest tests/test_validate.py::test_context_mode -x` | Wave 0 |
| GEN-01 | discogen run submits and polls with spinner | unit | `pytest tests/test_discogen.py::test_discogen_run -x` | Wave 0 |
| GEN-02 | discogen personas uses process-personas endpoint | unit | `pytest tests/test_discogen.py::test_discogen_personas -x` | Wave 0 |
| GEN-03 | Pre-flight cost estimate shown before submission | unit | `pytest tests/test_discogen.py::test_preflight_estimate -x` | Wave 0 |
| GEN-04 | Correct context mode choices per subcommand | unit | `pytest tests/test_discogen.py::test_context_modes -x` | Wave 0 |
| GEN-05 | --web-search warning when >50 domains | unit | `pytest tests/test_discogen.py::test_web_search_warning -x` | Wave 0 |
| GEN-06 | Interim results diff and display during polling | unit | `pytest tests/test_discogen.py::test_interim_results -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_validate.py tests/test_discogen.py tests/test_domain_input.py -x`
- **Per wave merge:** `pytest tests/ -v --cov=discolike`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_validate.py` — covers VAL-01 through VAL-04
- [ ] `tests/test_discogen.py` — covers GEN-01 through GEN-06
- [ ] `tests/test_domain_input.py` — covers D-01, D-02, D-03 (file, stdin, inline, CSV sniffing, 10k cap)
- [ ] `tests/fixtures/validate_completed.json` — real API response shape for completed validate
- [ ] `tests/fixtures/discogen_interim.json` — in-progress response with `interim_results`
- [ ] `tests/fixtures/discogen_completed.json` — completed discogen response
- [ ] `tests/conftest.py` — shared `CliRunner`, `respx` mock fixtures

*(No existing test infrastructure detected — `tests/` directory is empty.)*

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Runtime | Assumed yes (project constraint) | — | — |
| pytest | Tests | In pyproject.toml dev deps | 8.0+ | — |
| respx | HTTP mocking | In pyproject.toml dev deps | 0.21+ | — |
| ruff | Linting | In pyproject.toml dev deps | 0.4+ | — |
| mypy | Type check | In pyproject.toml dev deps | 1.10+ | — |

Step 2.6: SKIPPED (no external dependencies beyond what's in pyproject.toml dev; existing install covers all needs).

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| asyncio/httpx.AsyncClient | Sync httpx + time.sleep polling | Phase 1 decision | No rewrite needed, simpler mental model |
| InquirerPy for interactive prompts | questionary 2.1.1 | Phase 1 research | Not relevant for Phase 2 (no interactive prompts) |
| Custom polling per command | AsyncTaskManager shared | Phase 1 | Phase 2 just calls .poll() |

**Deprecated/outdated:**
- N/A — this is a greenfield phase on top of Phase 1 infrastructure.

---

## Open Questions

1. **`on_result` callback for interim results**
   - What we know: `AsyncTaskManager.poll()` has `on_status(status, attempt, elapsed)` but no access to the full response dict on intermediate polls
   - What's unclear: Is it cleaner to extend `poll()` with `on_result` or to have the discogen command manage its own polling loop?
   - Recommendation: Add `on_result: Callable[[dict[str, Any], int, float], None] | None = None` to `AsyncTaskManager.poll()`. Called with the full raw response dict on each iteration before sleep. Non-breaking addition. This keeps interim result logic out of the polling infrastructure while still making it accessible.

2. **Cost estimate rates for discogen**
   - What we know: D-08 says "Credits + model fees" for website/profile context modes, "model fees only" for domain mode. Exact per-domain rate not specified in API reference.
   - What's unclear: What are the actual credit rates per domain per context mode?
   - Recommendation: Display estimate as "credits + LLM fees (varies by content)" with `estimated_cost` from the submit response as the authoritative number once submitted. Pre-flight table shows context mode and domain count; actual cost shown in footer after completion via `estimated_cost` field from the final poll response.

3. **Discover pipe output format**
   - What we know: `OutputManager.render()` outputs JSON when stdout is not a TTY. JSON structure is `{"records": [...], "count": N}` with domain in each record.
   - What's unclear: Should `domain_input.py._read_stdin()` parse JSON records automatically, or document that users must use `discolike discover --csv --fields domain | discolike validate`?
   - Recommendation: Support both. If stdin starts with `{` or `[`, parse as JSON and extract `domain` field from each record. Otherwise parse as newline-separated plain text. This makes the pipe work ergonomically without extra flags.

---

## Sources

### Primary (HIGH confidence)
- `src/discolike/async_tasks.py` — AsyncTaskManager full interface, on_status callback signature
- `src/discolike/client.py:441-474` — submit method signatures and return shapes
- `src/discolike/output.py` — OutputManager render() behavior for non-TTY
- `src/discolike/types.py` — TaskSubmitResponse, TaskStatusResponse Pydantic models
- `leadgrow-hq/archive/mcp-docs/DiscoLike_API_Reference.md:1102-1230` — DiscoGen and Validate ICP endpoints, response flow, parameters, context modes
- `pyproject.toml` — test stack (pytest, respx), confirmed installed deps
- `CLAUDE.md` (project) — Rich + questionary interleaving warning, sync-only constraint

### Secondary (MEDIUM confidence)
- `reference/discolike-workflow.md` — pricing reference, API behavior patterns
- `.planning/phases/02-async-commands/02-CONTEXT.md` — all locked decisions D-01 through D-15

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in pyproject.toml, all Phase 1 assets verified by reading source
- Architecture: HIGH — direct extension of established patterns from discover.py and enrich.py
- API response shapes: HIGH — confirmed from official API reference in canonical_refs
- Pitfalls: HIGH — Pitfall 1 (on_result gap) confirmed by reading async_tasks.py source; Pitfall 3 (pipe format) confirmed by reading OutputManager source; others from CLAUDE.md warnings and Click/Rich behavior
- Test gaps: HIGH — `tests/` directory confirmed empty via Glob

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable stack, no fast-moving deps)
