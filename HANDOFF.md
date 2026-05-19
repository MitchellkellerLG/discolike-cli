# HANDOFF — discolike-cli TDD for New Commands

**Date:** 2026-05-18
**Commit:** 20613a5 — feat: wrap remaining 6 API endpoints — 100% surface coverage (25/25)
**Handoff from:** Claude Code session — Mitchell Keller

---

## What Was Built

7 new CLI commands wrapping previously unwrapped API endpoints:

| Command | Endpoint | Async? | Plan Gate |
|---|---|---|---|
| `discolike llm-providers list` | GET /llm-providers | No | None |
| `discolike llm-providers set` | POST /llm-providers | No | None |
| `discolike search-providers list` | GET /search-providers | No | None |
| `discolike search-providers set` | POST /search-providers | No | None |
| `discolike segment` | POST /segment | Yes (poll) | Pro+ |
| `discolike contacts match` | GET /contacts/match | No | Team+ |
| `discolike contacts bulk-match` | POST /contacts/bulk-match | No | Team+ |
| `discolike match bulk` | POST /match/bulk | No | Team+ |

Plus one refactor: `discolike append` switched from serial `/bizdata` calls to single `POST /append`.

`contacts` and `match` were upgraded from plain commands to Click groups with `invoke_without_command=True` — backward compatible.

---

## Current Test Coverage

**318 tests pass.** Core coverage is good:

| Area | Tests | Status |
|---|---|---|
| Client + cache + cost | 110 | Solid |
| Discover/count filters | 32 | Solid |
| Async task infrastructure | 73 | Solid |
| Config/account/extract | 18 | Adequate |
| Plan gate | 12 | Solid |
| Workflow | 15 | Adequate |
| **New commands** | **0** | **Needs tests** |
| **contacts (CLI layer)** | **0** | **Needs tests** |
| **match (CLI layer)** | **0** | **Needs tests** |
| **append (CLI layer)** | **0** | **Needs tests** |
| **vendors** | **0** | **Needs tests** |
| **subsidiaries** | **0** | **Needs tests** |

---

## TDD Plan

### Test Pattern

All tests use `click.testing.CliRunner` + mocked `DiscoLikeClient`. Example from existing tests:

```python
from click.testing import CliRunner
from unittest.mock import patch

def test_discover_basic():
    runner = CliRunner()
    with patch("discolike.cli.DiscoLikeClient") as MockClient:
        instance = MockClient.return_value
        instance.discover.return_value = DiscoverResult(
            records=[DiscoverRecord(domain="acme.com", name="Acme")],
            count=1,
        )
        instance.cost_tracker.last_call = CostBreakdown(
            endpoint="discover", total=Decimal("0.22"), plan="starter"
        )
        result = runner.invoke(cli, ["discover", "--domain", "acme.com", "--max-records", "1"])
        assert result.exit_code == 0
        assert "acme.com" in result.output
```

### Test Files to Create

#### 1. `tests/commands/test_llm_providers.py` (~8 tests)

```
- test_list_empty: GET /llm-providers returns {} → shows "No results"
- test_list_with_providers: returns {"openai": {...}} → table renders
- test_set_basic: --provider openai --api-key sk-xxx → POST succeeds
- test_set_with_model: includes --model gpt-4o
- test_set_with_base_url: includes --base-url for self-hosted
- test_dry_run: --dry-run flag, no API call
- test_json_output: --json flag → parseable JSON
- test_missing_required: --provider without --api-key → UsageError
```

#### 2. `tests/commands/test_search_providers.py` (~6 tests)

Same pattern as llm-providers. List, set, dry-run, JSON output, missing fields.

#### 3. `tests/commands/test_segment.py` (~8 tests)

```
- test_basic: --domain acme.com --yes → submits, polls, renders clusters
- test_with_input_file: --input domains.csv --yes
- test_interactive_confirm: no --yes, TTY → prompts for confirmation
- test_no_input: no --input, no --domain, no stdin → UsageError
- test_task_timeout: poll returns timeout → TaskTimeoutError
- test_task_failed: poll returns failed → TaskError
- test_cost_estimate: --dry-run shows estimate table
- test_plan_gate: on Starter plan → PlanGateError (exit code 4)
```

#### 4. `tests/commands/test_contacts.py` (~12 tests)

```
- test_contacts_search: --domain acme.com (backward compat)
- test_contacts_search_output: --output results.json
- test_contacts_search_missing_domain: no --domain → UsageError
- test_contacts_match: --name "Jane Doe"
- test_contacts_match_with_company: --name "Jane" --company "Acme"
- test_contacts_bulk_match: --name "Jane Doe" --name "John Smith"
- test_contacts_bulk_match_file: --input names.csv
- test_contacts_bulk_match_stdin: pipe JSON via stdin
- test_contacts_bulk_match_csv_no_name_column: CSV without name col → error
- test_contacts_bulk_match_large_confirm: >100 names, TTY → prompts
- test_contacts_plan_gate: on Starter → PlanGateError (exit code 4)
- test_contacts_json_output: --json flag
```

#### 5. `tests/commands/test_match.py` (~8 tests)

```
- test_match_single: "Acme Corp" (backward compat)
- test_match_no_args: no company name, no subcommand → UsageError
- test_match_bulk: --name "Acme" --name "Beta"
- test_match_bulk_file: --input names.csv
- test_match_bulk_stdin: pipe names via stdin
- test_match_bulk_large_confirm: >100 names → prompts
- test_match_plan_gate: on Starter → PlanGateError (exit code 4)
- test_match_json_output: --json flag
```

#### 6. `tests/commands/test_append.py` (~6 tests)

```
- test_append_basic: --input domains.csv --fields name,score --output out.csv
- test_append_csv_output: output is valid CSV with requested columns
- test_append_json_output: --output out.json
- test_append_empty_file: input file has no domains → ValidationError
- test_append_dry_run: --dry-run estimates cost
- test_append_no_input: missing --input → UsageError
```

### Fixtures Needed

Add to `tests/fixtures/`:

```
llm_providers_empty.json       → {}
llm_providers_list.json        → {"openai": {"model": "gpt-4o"}, "anthropic": {...}}
llm_providers_set_response.json → {"provider": "openai", "status": "configured"}
search_providers_empty.json    → {}
search_providers_list.json     → {"serper": {...}}
segment_completed.json         → {"task_id": "...", "status": "completed", "clusters": {...}}
segment_in_progress.json       → {"task_id": "...", "status": "in_progress", "progress": 50}
contact_match_result.json      → {"name": "Jane Doe", "domain": "acme.com", "email": "jane@acme.com", "title": "CEO"}
contact_bulk_match_result.json → {"results": [{"name": "Jane", "domain": "acme.com"}, ...]}
bulk_match_result.json         → {"results": [{"name": "Acme Corp", "domain": "acme.com"}, ...]}
append_result.json             → {"results": [{"domain": "acme.com", "name": "Acme", "score": 450}, ...]}
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run just new test files
pytest tests/commands/test_llm_providers.py tests/commands/test_search_providers.py tests/commands/test_segment.py tests/commands/test_contacts.py tests/commands/test_match.py tests/commands/test_append.py -v

# Coverage check
pytest tests/ --cov=discolike --cov-report=term-missing
```

---

## Manual Validation Needed

These areas cannot be fully tested without a live API key:

1. **append batch POST** — verify the real /append endpoint accepts {"domains": [...], "fields": [...]} and returns {"results": [...]}. If the response shape differs, update client.append().

2. **segment polling** — verify the polling endpoint at /discogen/status/{task_id} works for segment tasks (shared with discogen/validate).

3. **llm-providers set** — verify the POST body shape. Current assumption: {"provider": "openai", "api_key": "sk-...", "model": "gpt-4o"}.

4. **search-providers set** — same concern. Current assumption: {"provider": "serper", "api_key": "..."}.

5. **contact-bulk-match** — verify POST body shape. Current assumption: {"contacts": [{"name": "Jane", "company": "Acme"}, ...]}.

---

## Known Gaps (Out of Scope for This Handoff)

- workflow enrich-list still calls business_profile() serially (not using /append)
- Growth endpoint caching (7-day TTL matching profile/score)
- Domain normalization in domain_input.py (www prefix stripping, lowercasing)
- discolike doctor command for connectivity validation
- No OpenAPI spec from DiscoLike — all response shapes inferred from field reference

---

Repo: https://github.com/MitchellkellerLG/discolike-cli
PRD: discolike-cli/PRD.md
Handoff author: Mitchell Keller, mitchell@leadgrow.ai
