# discolike-cli

Python CLI for the DiscoLike B2B company discovery API. Wraps all endpoints with cost tracking, dual output, and agent-native design.

## Quick Start

```bash
pip install -e ".[dev]"
export DISCOLIKE_API_KEY="dk_..."
discolike --version
```

## Architecture

- **Entry point:** `src/discolike/cli.py` — Click group, `CliContext` dataclass, lazy client init
- **HTTP client:** `src/discolike/client.py` — httpx with retry/backoff, cache integration
- **Models:** `src/discolike/types.py` — Pydantic v2 for all API response shapes
- **Config:** `src/discolike/config.py` — API key resolution, `~/.discolike/config.yaml`
- **Constants:** `src/discolike/constants.py` — base URL, auth header, cache TTLs, plan pricing, CATEGORIES, EMPLOYEE_RANGES
- **Cost tracking:** `src/discolike/cost.py` — per-call + session totals
- **Output:** `src/discolike/output.py` — Rich tables / JSON / CSV
- **Errors:** `src/discolike/errors.py` — typed error hierarchy + `@handle_errors` decorator
- **Cache:** `src/discolike/cache.py` — SQLite at `~/.discolike/cache.db` with TTL + cost + task tables
- **Async tasks:** `src/discolike/async_tasks.py` — `AsyncTaskManager` for poll/cancel/resume lifecycle (discogen, validate, segment)
- **Domain input:** `src/discolike/domain_input.py` — shared domain arg parsing/validation
- **Commands:** `src/discolike/commands/` — one file per command group
- **Exporters:** `src/discolike/exporters/` — CSV/JSON writers

## Commands

| Command | Description |
|---------|-------------|
| `config` | Set/get config (api_key, etc.) |
| `account` | Account status and usage |
| `discover` | Find lookalike companies |
| `count` | Count results without fetching |
| `profile` | Business profile enrichment |
| `score` | ICP score enrichment |
| `growth` | Growth signals enrichment |
| `extract` | Extract companies from a URL |
| `saved` | Manage saved queries and exclusion lists |
| `costs` | Show session cost summary |
| `contacts` | Contact enrichment (Team+ plan) |
| `match` | Domain matching (Team+ plan) |
| `append` | Bulk append enrichment data |
| `vendors` | Vendor detection (Team+ plan) |
| `subsidiaries` | Subsidiary lookup (Enterprise plan) |
| `workflow` | Composite discover + enrich pipeline |
| `discogen` | AI-powered domain/persona enrichment (async) |
| `validate` | ICP validation (async) |

## Key Patterns

1. **stderr for progress, stdout for data:** never mix progress with parseable output
2. **Exit codes 1-6:** 1=APIError, 2=AuthError, 3=RateLimit, 4=PlanGate, 5=BudgetExceeded, 6=ValidationError
3. **Cost on every call:** displayed in footer (table) or `_meta.cost` (JSON)
4. **Cache with TTL:** account-status (1h), extract (90d), profile/score (7d)
5. **Plan-gated commands:** `contacts`/`match`/`vendors` require Team+; `subsidiaries` requires Enterprise. Gate checked via `@require_plan` decorator in `plan_gate.py`
6. **Async task pattern:** discogen/validate/segment return `task_id` — poll via `AsyncTaskManager`, state persisted in cache DB `tasks` table. No asyncio, sync httpx only.
7. **`--dry-run` flag:** estimates cost without making API calls

## API Reference

- Auth header: `x-discolike-key`
- Base URL: `https://api.discolike.com/v1`
- Full PRD: `PRD.md` (16 user stories, functional requirements, architecture)

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
- No live API calls in CI (gated behind `DISCOLIKE_API_KEY` env var)

## Gotchas

- **`questionary` is NOT a dependency** — interactive OLM loop is planned (v2 backlog) but not yet implemented. Do not import it.
- **Sync-only httpx** — the client uses `httpx` sync, not `AsyncClient`. No asyncio anywhere. Async task polling is a `while` loop with `time.sleep`, not coroutines.
- **Click + mypy** — `cli.py` and `commands/*` have `disable_error_code` overrides for known Click/mypy compat issues. Don't fight them.
- **Cache DB holds three tables:** `cache` (TTL data), `costs` (session cost log), `tasks` (async task state). Cost log is session-scoped — `discolike costs reset` clears it.
- **Plan pricing in constants.py** — pricing is local approximation for dry-run/display. Authoritative pricing comes from the API's account status response.
- **Windows-native** — CLI runs on Windows (dev machine). Avoid Unix-only libraries.
