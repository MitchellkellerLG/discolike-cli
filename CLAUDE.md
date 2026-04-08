# discolike-cli

Python CLI for the DiscoLike B2B company discovery API. Wraps all endpoints with cost tracking, dual output, and agent-native design.

## Quick Start

```bash
pip install -e ".[dev]"
export DISCOLIKE_API_KEY="dk_..."
discolike --version
```

## Architecture

- **Entry point:** `src/discolike/cli.py` (Click group)
- **HTTP client:** `src/discolike/client.py` (httpx with retry/backoff)
- **Models:** `src/discolike/types.py` (Pydantic v2 for all API shapes)
- **Cost tracking:** `src/discolike/cost.py` (per-call + session totals)
- **Output:** `src/discolike/output.py` (Rich tables / JSON / CSV)
- **Cache:** `src/discolike/cache.py` (SQLite at ~/.discolike/cache.db)
- **Commands:** `src/discolike/commands/` (one file per command group)
- **Exporters:** `src/discolike/exporters/` (CSV/JSON writers)

## Key Patterns

1. **Shared filters:** `count` and `discover` share filter options via Click decorator
2. **stderr for progress, stdout for data:** never mix progress with parseable output
3. **Exit codes 0-6:** each maps to a specific failure mode (see PRD US-016)
4. **Cost on every call:** displayed in footer (table) or `_meta.cost` (JSON)
5. **Cache with TTL:** account-status (1h), extract (90d), profile/score (7d)

## Dev Commands

```bash
pytest tests/ -v --cov=discolike    # Run tests
ruff check src tests                 # Lint
mypy src                             # Type check
```

## Testing

- Mock httpx with `respx` library
- CLI tests via `click.testing.CliRunner`
- Fixtures in `tests/fixtures/` (real API response shapes)
- No live API calls in CI (gated behind DISCOLIKE_API_KEY env var)

## API Reference

- Auth header: `x-discolike-key`
- Base URL: `https://api.discolike.com/v1/`
- Full field reference: `reference/discolike-field-reference.md`
- Workflow reference: `reference/discolike-workflow.md`
- Official docs: https://api.discolike.com/v1/docs/

## PRD

Full product requirements: `PRD.md` (16 user stories, functional requirements, architecture)

<!-- GSD:project-start source:PROJECT.md -->
## Project

**DiscoLike CLI v2 — OLM Feedback Loop & AI Discovery**

Upgrade the DiscoLike CLI from a one-shot discovery tool into a full discovery-to-action pipeline. Adds the OLM feedback loop (query plan confirmation and iterative refinement), ICP validation, AI-powered enrichment via DiscoGen, and auto-segmentation. Paired with an interactive multi-dimensional discovery skill that guides users through building precise lookalike queries across product, buyer, industry, size, and geo dimensions.

**Core Value:** The feedback loop between Claude Code's client context and DiscoLike's search model — both models iterate on the query plan until convergence, then run full TAM queries with confidence.

### Constraints

- **API**: Build against documented endpoints only — no undocumented/beta endpoints
- **Async operations**: DiscoGen, Validate ICP, and Segment are all async (task_id → poll → results). Need consistent async task management pattern
- **Rate limits**: 5 req/min on discover (Starter), 2 req/min on segment. Feedback loop iterations consume quota
- **Cost awareness**: Every API call costs money. Feedback loop iterations should be explicit about cumulative cost
- **Backwards compatibility**: Existing `discover` command behavior unchanged without `--confirm` flag
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

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
## New Stack Additions
### 1. Interactive Prompts — questionary 2.1.1
- **vs. Click's built-in prompts** — Click's `click.prompt()` and `click.confirm()` are adequate for single yes/no gates but have no multi-select, no styled selection menus, and no in-place edit flow. Building an iterative query review UI on raw Click would require 200+ lines of custom prompt logic. questionary collapses that to ~20 lines.
- **vs. InquirerPy** — InquirerPy has richer styling options but its last PyPI release was 2023. Maintenance is inactive. questionary 2.1.1 shipped August 2025 and is actively maintained.
- **vs. python-inquirer** — Unix-only (blessed library dependency), experimental Windows. Disqualified — this CLI runs on Windows (confirmed from env context).
- **vs. prompt_toolkit directly** — questionary IS a thin wrapper over prompt_toolkit 3.x. Using raw prompt_toolkit for this problem would be over-engineering. questionary exposes exactly the API shape needed: `select`, `checkbox`, `text`, `confirm`.
# Query plan field-by-field review
# Phrase match multi-select (accept/drop individual phrases)
# Free-text edit for icp_text override
# Final confirm before full TAM query (rate limit + cost gate)
### 2. Async Task Polling — no new library, pure stdlib pattern
- `tenacity` / `backoff` are designed for "retry until success after transient failures." They use exception-driven flow. Task polling is not an exception — a `pending` status is expected and normal.
- The existing `DiscoLikeClient._request()` already handles transient failures (5xx, connection errors) with exponential backoff. No duplication needed.
- Adding tenacity just for polling would import a retry framework to solve a `while status != "complete": sleep(N)` problem.
- Starts at 3s interval, backs off to 15s max (reduces quota pressure on DiscoLike)
- Hard stops at 5 minutes (segment/discogen SLA)
- Uses existing `DiscoLikeClient` — no new HTTP infrastructure
- Is fully synchronous — no asyncio, no threads. Matches the existing sync httpx client.
### 3. Streaming Progress Display — Rich (already installed)
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
## Updated pyproject.toml Dependencies
## Pitfall: Rich + questionary Output Interleaving
## Sources
- questionary PyPI: https://pypi.org/project/questionary/ — version 2.1.1, Aug 28 2025 (HIGH confidence)
- Rich PyPI: https://pypi.org/project/rich/ — version 14.3.3, Feb 2026 (HIGH confidence)
- prompt_toolkit stdin/TTY issue: https://github.com/prompt-toolkit/python-prompt-toolkit/issues/502 (MEDIUM confidence — known issue documented in upstream)
- InquirerPy maintenance status: https://snyk.io/advisor/python/inquirerpy (MEDIUM confidence)
- sys.stdin.isatty() pattern: https://gist.github.com/rduplain/e063114479e7470db8d3 (MEDIUM confidence)
- Tenacity: https://tenacity.readthedocs.io/ (HIGH confidence — deliberately excluded)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
