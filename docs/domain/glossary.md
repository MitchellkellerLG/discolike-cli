# Ubiquitous Language Glossary

Terms extracted from source code. Use these names exactly in code, docs, and issues.

| Term | Definition | Key Files |
|------|-----------|-----------|
| `CliContext` | Dataclass passed through all Click commands via `ctx.obj`. Holds client, output manager, cost tracker, cache, and global flags (dry_run, json_output, etc.). | `src/discolike/cli.py` |
| `DiscoLikeClient` | The single HTTP client for all API endpoints. Owns retry/backoff logic, cache integration, cost tracking, and dry_run short-circuiting. | `src/discolike/client.py` |
| `CostTracker` | Tracks per-call and session API costs using plan-based pricing. Emits budget warnings at 80%/95% and raises `BudgetExceededError` at 100%. | `src/discolike/cost.py` |
| `CacheManager` | SQLite-backed local cache at `~/.discolike/cache.db`. Manages three tables: `cache` (TTL data), `costs` (session cost log), `tasks` (async task state). | `src/discolike/cache.py` |
| `AsyncTaskManager` | Manages poll/cancel/resume lifecycle for async API tasks (discogen, validate, segment). Uses sync `while` + `time.sleep`, not asyncio. | `src/discolike/async_tasks.py` |
| `PlanPricing` | NamedTuple encoding per-query and per-1k-record prices for each plan tier (starter, pro, team, company, enterprise). | `src/discolike/constants.py` |
| `plan_gate` / `@require_plan` | Decorator that checks the user's current plan level against `PLAN_GATED_FEATURES` before executing a command. Raises `PlanGateError` if insufficient. | `src/discolike/commands/plan_gate.py` |
| `@handle_errors` | Decorator on every command function. Catches all `DiscoLikeError` subclasses, renders them to stderr (or JSON stdout), and calls `sys.exit(e.exit_code)`. | `src/discolike/errors.py` |
| `dry_run` | Global flag that short-circuits all API calls. Cost estimates are computed and displayed, but no HTTP request is made. Controlled by `--dry-run` global option. | `src/discolike/cli.py`, `src/discolike/client.py` |
| `DiscoverRecord` | Pydantic model for a single company returned by the `/discover` endpoint. Uses `extra="allow"` to absorb new API fields without breaking. | `src/discolike/types.py` |
| `DiscoverResult` | Container for a list of `DiscoverRecord` items plus a total `count`. The discover endpoint may return a bare JSON array; client normalizes it. | `src/discolike/types.py` |
| `collect_filters` | Function in `discover.py` that converts Click kwargs to the API filter dict. Strips empty tuples, False flags, and API-default values. | `src/discolike/commands/discover.py` |
| `discovery_filters` | Decorator factory that attaches all 27 shared filter options to both the `count` and `discover` commands. | `src/discolike/commands/discover.py` |
| `task_id` | String identifier returned by async submission endpoints (`/discogen/process`, `/validate/icp`, `/segment`). Used to poll `/discogen/status/{task_id}`. | `src/discolike/types.py`, `src/discolike/async_tasks.py` |
| `OutputManager` | Renders command output as Rich tables (TTY), JSON (pipe/`--json`), or CSV (`--csv`). Progress and warnings always go to stderr. | `src/discolike/output.py` |
| `AUTH_HEADER` | The literal string `x-discolike-key` used as the HTTP authentication header name. | `src/discolike/constants.py` |
| `PLAN_LEVELS` | Ordered list of plan names used to compute ordinal plan comparisons for gate checks: `["starter", "pro", "team", "company", "enterprise"]`. | `src/discolike/constants.py` |
| `PLAN_GATED_FEATURES` | Dict mapping command names to minimum plan strings. Controls which commands require `team` or `enterprise`. | `src/discolike/constants.py` |
| `exclusion_query_id` | API parameter on `/discover` that references a saved exclusion list by ID. Prevents returning previously seen domains. | `src/discolike/client.py`, `src/discolike/commands/discover.py` |
| `CostBreakdown` | Pydantic model capturing query_fee, record_fee, total, and session_total for a single API call. Attached to every output render. | `src/discolike/types.py` |
