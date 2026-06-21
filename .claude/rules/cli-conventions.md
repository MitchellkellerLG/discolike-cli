---
paths:
  - "src/discolike/commands/**/*.py"
  - "src/discolike/cli.py"
---

# CLI Command Conventions

## Output discipline

stderr for progress and errors, stdout for parseable data. Never mix them.
Use `click.secho(..., err=True)` for user-facing messages. Use `click.echo()` for data output.

## Error handling

Every command function must be decorated with `@handle_errors` from `discolike.errors`.
Raise typed errors (`APIError`, `AuthError`, `RateLimitError`, `PlanGateError`, `BudgetExceededError`, `ValidationError`) -- never call `sys.exit()` directly.

## Exit codes

1=APIError, 2=AuthError, 3=RateLimit, 4=PlanGate, 5=BudgetExceeded, 6=ValidationError. Do not invent new codes without updating `errors.py`.

## New commands

One file per command group in `src/discolike/commands/`. Register in `cli.py` via `cli.add_command()`. Include cost tracking on every API call.

## Sync only

httpx sync client only. No `AsyncClient`, no `asyncio`. Async task polling uses `while` + `time.sleep`, not coroutines.

## Plan gating

Commands restricted to higher plans use the `@require_plan` decorator from `plan_gate.py`. Do not inline plan checks.
