# Triage Labels

Five canonical states for all issues in discolike-cli.

| Label | When to Apply | Who Acts Next | Example |
|-------|--------------|---------------|---------|
| `needs-triage` | New issue, not yet reviewed by a human | Maintainer reviews within 48h | Any freshly opened GitHub issue |
| `needs-info` | Issue is too vague or missing reproduction steps | Reporter must supply details | "it crashes" with no command shown |
| `ready-for-agent` | Scoped, reproducible, and bounded to known code paths | AI agent can attempt a fix | "CostTracker.estimate does not accumulate to session — confirm this is intentional" |
| `ready-for-human` | Requires judgment, external access, or API-key-gated testing | Human engineer owns it | Plan-gate logic broken when API returns unexpected plan string |
| `wontfix` | Intentionally not addressing — documented reason required | Maintainer closes with comment | questionary interactive OLM loop (backlog, not planned for v1) |

## Applying Labels

- Apply exactly one state label per issue at all times.
- When state changes, remove the old label before adding the new one.
- `needs-triage` is the default for all new issues — never leave an issue unlabeled.

## ready-for-agent Criteria

An issue is ready for an agent when:
1. The failing behavior is reproduced with a specific command or code path.
2. The relevant source module is identified (`client.py`, `cost.py`, `cache.py`, etc.).
3. No live API key or external service access is required to verify the fix.
4. A test can be written without touching `.env` or real network calls (use `respx` mocks).
