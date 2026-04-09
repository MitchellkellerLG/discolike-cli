# Technology Stack

**Project:** DiscoLike CLI v2 — OLM Feedback Loop & AI Discovery
**Researched:** 2026-04-08
**Scope:** Additive stack for async task polling, interactive CLI feedback loops, and streaming progress — layered on the existing Click/httpx/Rich/Pydantic v2/SQLite foundation.

---

## Existing Stack (Do Not Revisit)

| Technology | Version | Role |
|------------|---------|------|
| Python | 3.11+ | Runtime |
| Click | 8.1.x | CLI framework |
| httpx | 0.27+ | HTTP client (sync) |
| Rich | 13.x | Tables, progress, console output |
| Pydantic v2 | 2.x | API response models |
| PyYAML | 6.x | Config |
| SQLite | stdlib | Local cache |

All of the above are confirmed in `pyproject.toml`. No version changes needed.

---

## New Stack Additions

### 1. Interactive Prompts — questionary 2.1.1

**Purpose:** Review/adjust loops for the OLM feedback cycle (LOOP-01 through LOOP-03). Presents the query plan (lookalike text, phrase matches, industry groups, filters), lets the user edit fields inline, confirm, or resubmit.

**Why questionary over alternatives:**

- **vs. Click's built-in prompts** — Click's `click.prompt()` and `click.confirm()` are adequate for single yes/no gates but have no multi-select, no styled selection menus, and no in-place edit flow. Building an iterative query review UI on raw Click would require 200+ lines of custom prompt logic. questionary collapses that to ~20 lines.
- **vs. InquirerPy** — InquirerPy has richer styling options but its last PyPI release was 2023. Maintenance is inactive. questionary 2.1.1 shipped August 2025 and is actively maintained.
- **vs. python-inquirer** — Unix-only (blessed library dependency), experimental Windows. Disqualified — this CLI runs on Windows (confirmed from env context).
- **vs. prompt_toolkit directly** — questionary IS a thin wrapper over prompt_toolkit 3.x. Using raw prompt_toolkit for this problem would be over-engineering. questionary exposes exactly the API shape needed: `select`, `checkbox`, `text`, `confirm`.

**Confidence:** HIGH — version confirmed via PyPI (2.1.1, Aug 28 2025). Active maintenance confirmed. prompt_toolkit foundation confirmed.

**Key APIs for this project:**

```python
# Query plan field-by-field review
result = questionary.select(
    "auto_icp_text result:",
    choices=["Accept", "Edit", "Regenerate"],
).ask()

# Phrase match multi-select (accept/drop individual phrases)
kept = questionary.checkbox(
    "Keep which phrase matches?",
    choices=applied_phrases,
).ask()

# Free-text edit for icp_text override
new_icp = questionary.text(
    "Edit ICP description:",
    default=current_icp_text,
).ask()

# Final confirm before full TAM query (rate limit + cost gate)
confirmed = questionary.confirm(
    f"Submit full TAM query (~{cost_estimate})?"
).ask()
```

**Non-interactive guard (CRITICAL):** questionary raises `AssertionError` from prompt_toolkit when stdin is not a TTY (piped, CI, agent-driven). This is a known upstream constraint. The `--confirm` flag that enables the feedback loop MUST be gated by a TTY check:

```python
import sys

if not sys.stdin.isatty():
    raise click.UsageError(
        "--confirm requires an interactive terminal. "
        "Run without --confirm for one-shot mode."
    )
```

This guard preserves the CLI's agent-native design — agents run one-shot (no `--confirm`), humans run interactive.

**Pin:** `questionary>=2.1,<3.0`

---

### 2. Async Task Polling — no new library, pure stdlib pattern

**Purpose:** Poll DiscoGen (`/discogen/process`), Validate ICP (`/validate/icp`), and Segment (`/segment`) until completion. All three use `task_id → GET status → results` pattern.

**Why no library (tenacity, backoff, etc.):**

The task polling problem here is NOT a retry-on-failure problem. It is a deliberate wait-for-completion polling loop with bounded intervals. The distinction matters:

- `tenacity` / `backoff` are designed for "retry until success after transient failures." They use exception-driven flow. Task polling is not an exception — a `pending` status is expected and normal.
- The existing `DiscoLikeClient._request()` already handles transient failures (5xx, connection errors) with exponential backoff. No duplication needed.
- Adding tenacity just for polling would import a retry framework to solve a `while status != "complete": sleep(N)` problem.

**Use this stdlib pattern instead:**

```python
import time

def poll_task(
    client: DiscoLikeClient,
    task_id: str,
    endpoint: str,
    poll_interval: float = 3.0,
    max_wait: float = 300.0,
    backoff_factor: float = 1.5,
    max_interval: float = 15.0,
) -> dict:
    """Poll a task endpoint until status is 'complete' or 'failed'."""
    elapsed = 0.0
    interval = poll_interval
    while elapsed < max_wait:
        result = client._get_with_params(endpoint, {"task_id": task_id})
        status = result.get("status")
        if status == "complete":
            return result
        if status == "failed":
            raise APIError(f"Task {task_id} failed: {result.get('error')}")
        time.sleep(interval)
        elapsed += interval
        interval = min(interval * backoff_factor, max_interval)
    raise APIError(f"Task {task_id} timed out after {max_wait}s.")
```

This pattern:
- Starts at 3s interval, backs off to 15s max (reduces quota pressure on DiscoLike)
- Hard stops at 5 minutes (segment/discogen SLA)
- Uses existing `DiscoLikeClient` — no new HTTP infrastructure
- Is fully synchronous — no asyncio, no threads. Matches the existing sync httpx client.

**Note on asyncio:** The existing client uses `httpx.Client` (sync). Adding `asyncio` to support `httpx.AsyncClient` would require converting every command handler to `async def` and wiring an event loop into Click. That is architectural scope not justified by polling 3 endpoints. Stay sync.

**Confidence:** HIGH — this is a first-principles implementation, verified against the API pattern in PROJECT.md and client.py. No library uncertainty.

---

### 3. Streaming Progress Display — Rich (already installed)

**Purpose:** Show live spinner + status text + elapsed time during task polling (DiscoGen, Validate ICP, Segment). Show iterative query plan display during OLM feedback loop.

**Why no new library:** Rich 14.x is already a dependency (`rich>=13.0` in pyproject.toml). Rich 14.3.3 (Feb 2026) confirmed installed.

**Key capabilities already available:**

**For async task polling (spinner + live status):**

```python
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

console = Console(stderr=True)  # keep stdout clean for data

with console.status(
    "[bold green]Processing DiscoGen task...",
    spinner="dots"
) as status:
    result = poll_task(
        client,
        task_id,
        endpoint="/discogen/status",
        on_tick=lambda elapsed: status.update(
            f"[bold green]Processing... ({elapsed:.0f}s elapsed)"
        ),
    )
```

For richer displays (progress bar where total is unknown, or multi-step jobs), use `rich.live.Live` with `auto_refresh=False` and call `live.update(renderable)` + `live.refresh()` at each poll tick. `refresh_per_second` defaults to 4 — drop it to 1 for polling loops that update every 3-15s.

**For OLM feedback loop (query plan table display):**

```python
from rich.table import Table

def render_query_plan(plan: QueryPlan) -> Table:
    table = Table(title="Current Query Plan", show_header=True)
    table.add_column("Dimension", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("ICP Text", plan.icp_text or "[auto]")
    table.add_row("Phrase Matches", ", ".join(plan.phrase_matches))
    table.add_row("Industries", ", ".join(plan.industry_groups))
    # ...
    return table
```

Print the table between each questionary prompt cycle. Rich + questionary on the same console works cleanly — Rich renders static output, questionary takes control of stdin for the prompt, returns, Rich renders next output. No conflict.

**Confidence:** HIGH — Rich is already in the dependency tree. API confirmed from PyPI (14.3.3). `console.status()`, `rich.live.Live`, `rich.table.Table` are all stable Rich APIs.

---

## Summary: What to Add vs What to Reuse

| Need | Solution | New Dep? |
|------|----------|----------|
| Interactive review/adjust loop | `questionary>=2.1,<3.0` | YES — new |
| Multi-select checkboxes (phrase match accept/drop) | questionary checkbox | same |
| Non-interactive guard | `sys.stdin.isatty()` check | NO — stdlib |
| Task polling loop | Custom `poll_task()` with `time.sleep` | NO — stdlib |
| Spinner during task polling | `console.status()` from Rich | NO — already installed |
| Live status updates | `rich.live.Live` | NO — already installed |
| Query plan display | `rich.table.Table` | NO — already installed |
| OLM query plan rendering | Rich table + questionary prompts | NO new deps |

**Net new dependency:** `questionary>=2.1,<3.0` only. Zero other additions.

---

## What NOT to Use

| Library | Why Not |
|---------|---------|
| `asyncio` / `httpx.AsyncClient` | Would require full CLI rewrite. Polling doesn't need concurrency. |
| `tenacity` / `backoff` | Wrong abstraction — task polling is not retry-on-failure. |
| `InquirerPy` | Unmaintained since 2023. questionary is the maintained alternative. |
| `python-inquirer` | Unix-only. CLI runs on Windows. |
| `PyInquirer` | Abandoned. questionary is the active fork. |
| `prompt_toolkit` directly | Too low level for this problem. questionary wraps it correctly. |
| `click.prompt()` / `click.confirm()` | Fine for gates, not for multi-field interactive review loops. |
| `threading` for background polling | Unnecessary complexity. Sync polling with Rich status is clean and readable. |

---

## Updated pyproject.toml Dependencies

```toml
dependencies = [
    "click>=8.1,<8.2",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "rich>=13.0",
    "questionary>=2.1,<3.0",   # NEW — interactive OLM feedback loops
]
```

---

## Pitfall: Rich + questionary Output Interleaving

When using `rich.console.Console` AND questionary in the same command, both write to the terminal. This is safe as long as you are NOT inside a `rich.live.Live` context when questionary prompts run. The pattern:

```
1. Print Rich table (static)
2. questionary.select().ask()   ← questionary takes terminal
3. Print Rich table (static, updated)
4. questionary.confirm().ask()  ← confirm and submit
```

DO NOT wrap questionary calls inside `with Live(...)`. Live's refresh loop and prompt_toolkit's event loop will fight for terminal control and produce garbled output. Only use `Live` for the polling phase (no user input), never during the prompt phase.

---

## Sources

- questionary PyPI: https://pypi.org/project/questionary/ — version 2.1.1, Aug 28 2025 (HIGH confidence)
- Rich PyPI: https://pypi.org/project/rich/ — version 14.3.3, Feb 2026 (HIGH confidence)
- prompt_toolkit stdin/TTY issue: https://github.com/prompt-toolkit/python-prompt-toolkit/issues/502 (MEDIUM confidence — known issue documented in upstream)
- InquirerPy maintenance status: https://snyk.io/advisor/python/inquirerpy (MEDIUM confidence)
- sys.stdin.isatty() pattern: https://gist.github.com/rduplain/e063114479e7470db8d3 (MEDIUM confidence)
- Tenacity: https://tenacity.readthedocs.io/ (HIGH confidence — deliberately excluded)
