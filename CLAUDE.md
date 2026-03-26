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
