# Domain Layout

## Context Model

discolike-cli is **single-context**: one CLI process, one user, one API key. There is no multi-tenancy, no workspace switching, and no session isolation beyond the per-invocation `CliContext` dataclass.

## Domain Layout

The domain is organized into three concentric layers:

```
┌─────────────────────────────────────────────────────┐
│  CLI Layer (cli.py, commands/)                       │
│  User interaction, option parsing, output rendering  │
├─────────────────────────────────────────────────────┤
│  Service Layer (client.py, cost.py, cache.py,        │
│                 async_tasks.py)                      │
│  HTTP, caching, cost tracking, async task lifecycle  │
├─────────────────────────────────────────────────────┤
│  Domain Model (types.py, constants.py, errors.py)   │
│  Pydantic models, pricing, error hierarchy           │
└─────────────────────────────────────────────────────┘
```

## Where Domain Docs Live

| Document | Location |
|----------|----------|
| Ubiquitous language glossary | `docs/domain/glossary.md` |
| Architecture decision records | `docs/domain/adr/` |
| API reference and PRD | `PRD.md` (root) |
| CLI conventions and rules | `.claude/rules/cli-conventions.md` |
| Command reference | `CLAUDE.md` (root), `README.md` |

## Boundaries

The CLI has one external dependency boundary: the DiscoLike REST API at `https://api.discolike.com/v1`. All other state (config, cache, cost log, task history) is local to `~/.discolike/` on the user's machine.

There are no inter-process communication patterns, no daemon, and no network services started by the CLI itself.
