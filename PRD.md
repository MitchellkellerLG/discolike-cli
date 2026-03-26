# DiscoLike CLI — Product Requirements Document

## Context

DiscoLike is a B2B company discovery platform (65M+ domains, 180+ countries) currently accessed via MCP server in Claude Code. The MCP works but limits us to Claude-only usage. A standalone CLI unlocks:

- **Direct terminal usage** — humans can run discovery workflows without Claude
- **CI/CD integration** — automated prospect list generation in pipelines
- **Agent-native design** — any AI agent (not just Claude) can orchestrate it
- **Cost visibility** — built-in cost tracking per command and per session
- **Portability** — pip-installable, works on any machine with Python 3.11+

This CLI graduates DiscoLike from MCP-only to a first-class tool. It lives in its own GitHub repo (`discolike-cli`), is distributed via pip, and follows the CLI-Anything patterns (dual output, SKILL.md, structured exit codes) for maximum resilience.

**Pricing model:** Dual cost — per-query fee ($0.08–$0.18 depending on plan) + per-record fee ($1.50–$3.50 per 1K records). Starter plan: $99/mo, $0.18/query, $3.50/1K records.

---

## Goals

- [ ] Wrap ALL DiscoLike API endpoints as CLI commands (including plan-gated ones)
- [ ] Provide composite workflow commands that chain the 8-step discovery process
- [ ] Built-in cost tracking with per-call and session-total display
- [ ] Dual output: human-readable tables (default) + JSON for machines + CSV for exports
- [ ] Agent-native: predictable exit codes, structured errors, SKILL.md for discovery
- [ ] pip-installable standalone package in its own GitHub repo

---

## User Stories

### US-001: API Key Configuration

**As a** CLI user, **I want** to configure my DiscoLike API key once **so that** I don't have to pass it on every command.

**Acceptance Criteria:**

- [ ] API key loaded from `DISCOLIKE_API_KEY` env var (highest priority)
- [ ] API key loaded from `~/.discolike/config.yaml` (fallback)
- [ ] `discolike config set api_key <key>` writes to config file
- [ ] `discolike config show` displays current config (key source, plan, cache stats) with key partially masked
- [ ] Missing key produces clear error with setup instructions (exit code 2)
- [ ] Typecheck passes

### US-002: Account Status

**As a** CLI user, **I want** to check my DiscoLike account status **so that** I know my plan, spend, and remaining budget before running queries.

**Acceptance Criteria:**

- [ ] `discolike account status` returns plan name, MTD spend, remaining budget, request/record counts
- [ ] `discolike account usage` returns detailed monthly breakdown by user
- [ ] JSON output includes all fields from API response
- [ ] Table output shows a clean summary with budget bar
- [ ] Account status is cached locally (1-hour TTL) to avoid unnecessary API calls
- [ ] Plan level auto-detected and cached for cost tracker
- [ ] Typecheck passes

### US-003: Extract Website Text

**As a** CLI user, **I want** to extract cached website text for a domain **so that** I can analyze it to build ICP definitions before discovery.

**Acceptance Criteria:**

- [ ] `discolike extract <domain>` returns the cached website text
- [ ] Results cached locally (90-day TTL matching DiscoLike's cache)
- [ ] `--no-cache` flag forces fresh extraction
- [ ] Cost displayed after call ($0.18 query fee)
- [ ] Typecheck passes

### US-004: Count Matching Domains

**As a** CLI user, **I want** to count how many companies match my filters **so that** I can validate the market size before committing to a discovery query.

**Acceptance Criteria:**

- [ ] `discolike count` returns domain count matching filters
- [ ] All positive filters supported: `--domain`, `--icp-text`, `--phrase`, `--country`, `--state`, `--employees`, `--category`, `--language`, `--min-score`, `--max-score`
- [ ] All negation filters supported: `--negate-domain`, `--negate-icp-text`, `--negate-country`, `--negate-category`, `--negate-phrase`, `--negate-language`
- [ ] Filters shared with `discover` command (same option names and behavior)
- [ ] Count < 50 triggers a warning suggesting looser filters
- [ ] Count > 10,000 triggers a warning suggesting tighter filters
- [ ] Cost displayed ($0.18 query fee, no record cost)
- [ ] Typecheck passes

### US-005: Discover Similar Companies

**As a** CLI user, **I want** to find companies similar to seed domains or ICP descriptions **so that** I can build targeted prospect lists.

**Acceptance Criteria:**

- [ ] `discolike discover` returns matching companies with requested fields
- [ ] All filters from US-004 plus discovery-specific: `--max-records`, `--fields`, `--auto-icp`, `--auto-phrases`, `--enhanced`, `--include-seeds`, `--redirect`, `--variance`, `--consensus`, `--social`, `--negate-social`, `--min-similarity`, `--start-date`
- [ ] `--max-records` defaults to 10 (safe default matching skill guidance)
- [ ] Default fields: domain, name, similarity, score, employees, description
- [ ] `--output <file>` saves results to CSV or JSON (auto-detected from extension)
- [ ] `--exclude <query-id>` excludes a saved query's domains
- [ ] Cost displayed (query fee + record fee based on records returned)
- [ ] Table output truncates long descriptions with ellipsis
- [ ] Typecheck passes

### US-006: Business Profile Enrichment

**As a** CLI user, **I want** to get enriched firmographic data for a single domain **so that** I can deep-dive into a specific company.

**Acceptance Criteria:**

- [ ] `discolike profile <domain>` returns enriched company data
- [ ] `--fields` filters which fields are returned
- [ ] Results cached locally (7-day TTL)
- [ ] `--output <file>` saves to file
- [ ] Cost displayed ($0.18 query fee)
- [ ] Typecheck passes

### US-007: Digital Footprint Score

**As a** CLI user, **I want** to get a company's digital presence score **so that** I can assess their online maturity.

**Acceptance Criteria:**

- [ ] `discolike score <domain>` returns score (0-999) with breakdown parameters
- [ ] Results cached locally (7-day TTL)
- [ ] Table output shows score prominently with breakdown
- [ ] Typecheck passes

### US-008: Growth Metrics

**As a** CLI user, **I want** to see a company's growth trends **so that** I can identify growing companies.

**Acceptance Criteria:**

- [ ] `discolike growth <domain>` returns 3m/12m growth rates and quarterly scores
- [ ] Table output shows trend visualization (up/down arrows or sparkline)
- [ ] Typecheck passes

### US-009: Saved Queries & Exclusion Lists

**As a** CLI user, **I want** to save and manage exclusion lists **so that** I can avoid re-querying the same companies.

**Acceptance Criteria:**

- [ ] `discolike saved list` returns all saved queries
- [ ] `discolike saved save --name "Query Name" --domains domain1.com,domain2.com` saves an exclusion list
- [ ] `discolike saved save --name "Query Name" --input domains.csv` reads domains from file
- [ ] Typecheck passes

### US-010: Contacts Search

**As a** CLI user, **I want** to search for B2B contacts at a company **so that** I can find decision-makers.

**Acceptance Criteria:**

- [ ] `discolike contacts --domain <domain>` returns contacts
- [ ] `--title` filter for job title
- [ ] `--max-records` for result limit
- [ ] `--output <file>` for export
- [ ] Plan gate check: if Starter plan, show clear error with required plan level (exit code 4)
- [ ] Typecheck passes

### US-011: Plan-Gated Commands (Match, Append, Vendors, Subsidiaries)

**As a** CLI user, **I want** access to all API endpoints even if plan-gated **so that** I'm ready when I upgrade.

**Acceptance Criteria:**

- [ ] `discolike match <company-name>` resolves company name to domain (Team+)
- [ ] `discolike append --input <file> --fields <list> --output <file>` bulk-appends firmographic data (Starter+)
- [ ] `discolike vendors <domain>` returns tech stack (Team+)
- [ ] `discolike subsidiaries <domain>` returns corporate hierarchy (Enterprise)
- [ ] Each command pre-checks plan level from cached account-status
- [ ] Plan-gated commands show clear error: "The 'vendors' command requires Team plan or above. Current plan: Starter." (exit code 4)
- [ ] Typecheck passes

### US-012: Workflow — Full Discovery

**As a** CLI user, **I want** a single command that runs the complete 8-step discovery workflow **so that** I get a prospect list without manually chaining commands.

**Acceptance Criteria:**

- [ ] `discolike workflow discover --seed <domain> --country <code> --max-records <n>` runs the full workflow
- [ ] Steps executed in order: account-status check -> extract seed(s) -> count -> discover (10 for validation) -> discover (full) -> enrich top N -> export CSV -> save exclusion (optional)
- [ ] `--enrich-top <n>` controls how many results get business-profile enrichment (default: 5)
- [ ] `--output <file>` sets export path (auto-named if omitted: `{seed}-lookalikes-{YYYY-MM-DD}.csv`)
- [ ] `--save-exclusion` saves results as exclusion list
- [ ] `--no-confirm` skips interactive prompts (for automation/agents)
- [ ] In interactive mode: shows intermediate results and asks for confirmation before scaling up
- [ ] Running cost total displayed at each step
- [ ] Final summary: total cost, records found, file location, exclusion list ID
- [ ] Typecheck passes

### US-013: Workflow — Enrich List

**As a** CLI user, **I want** to enrich an existing list of domains with profiles, scores, and growth data **so that** I can add firmographic data to any domain list.

**Acceptance Criteria:**

- [ ] `discolike workflow enrich-list --input <file> --output <file>` enriches all domains
- [ ] `--fields profile,score,growth` controls which enrichment types to run (default: all)
- [ ] Progress bar shows enrichment progress
- [ ] Results merged into single output file
- [ ] Parallel execution for speed (respecting rate limits)
- [ ] Running cost displayed
- [ ] Typecheck passes

### US-014: Cost Tracking & Dry Run

**As a** CLI user, **I want** to see costs for every operation and preview costs before executing **so that** I never get surprised by spend.

**Acceptance Criteria:**

- [ ] Every command displays cost in its output footer (table mode) or `_meta.cost` block (JSON mode)
- [ ] Cost includes: this_call, query_fee, record_fee, session_total, budget_remaining, plan
- [ ] `--dry-run` on any command shows estimated cost without executing the API call
- [ ] `discolike costs` shows full session cost breakdown
- [ ] `discolike costs --reset` resets session counter
- [ ] Budget warnings at 80% consumption (stderr warning)
- [ ] Budget warnings at 95% consumption (stderr warning + confirmation prompt unless `--no-confirm`)
- [ ] Budget block at 100% consumption (exit code 5)
- [ ] Plan pricing auto-detected from account-status
- [ ] Typecheck passes

### US-015: Dual Output System

**As a** CLI user or AI agent, **I want** output that adapts to my context **so that** humans see readable tables and machines get parseable JSON.

**Acceptance Criteria:**

- [ ] TTY (terminal) -> Rich table with colors (default)
- [ ] Pipe/redirect -> JSON (auto-detected)
- [ ] `--json` flag forces JSON output even in TTY
- [ ] `--csv` flag forces CSV output
- [ ] `--fields` filters output columns in all modes
- [ ] `--quiet` suppresses stderr progress messages
- [ ] Progress/warnings always go to stderr (never pollute stdout data stream)
- [ ] Typecheck passes

### US-016: Error Handling & Exit Codes

**As an** AI agent, **I want** predictable exit codes and structured error output **so that** I can programmatically handle failures.

**Acceptance Criteria:**

- [ ] Exit code 0: success
- [ ] Exit code 1: generic API error
- [ ] Exit code 2: auth error (missing/invalid key)
- [ ] Exit code 3: rate limited (with retry-after info)
- [ ] Exit code 4: plan gate (feature requires higher plan)
- [ ] Exit code 5: budget exceeded
- [ ] Exit code 6: invalid input / validation error
- [ ] JSON error output: `{"error": "message", "code": "ERROR_CODE", "suggestion": "..."}`
- [ ] Table error output: colored message with suggestion on stderr
- [ ] HTTP client retries 429/5xx with exponential backoff (3 attempts) before surfacing error
- [ ] Typecheck passes

---

## Functional Requirements

### FR-1: HTTP Client

- Base URL: `https://api.discolike.com/v1/`
- Auth: `x-discolike-key` header
- Library: `httpx` (connection pooling, proper timeouts, async-ready)
- Retry: exponential backoff on 429/5xx, respect `Retry-After` header, max 3 attempts
- Rate limit tracking: parse rate limit headers, warn at 80% consumption
- Every method returns a Pydantic model, not raw dict

### FR-2: Configuration

- Precedence: env var `DISCOLIKE_API_KEY` > `~/.discolike/config.yaml` > error
- Config file supports: `api_key`, `plan` (auto-detected), `default_country`, `default_fields`, `output_dir`
- `discolike config set/show/clear` commands for management
- Plan auto-detected on first API call and cached

### FR-3: Local Cache

- SQLite-backed at `~/.discolike/cache.db`
- TTLs: account-status (1 hour), extract (90 days), profile (7 days), score (7 days)
- Discovery results NOT cached (filter-dependent)
- `--no-cache` global flag bypasses cache
- `discolike config show` includes cache stats

### FR-4: Cost Tracking

- Pricing table for all 5 plans hardcoded in `constants.py`
- Cost formula: `query_fee + (records_returned / 1000) * record_fee`
- Session-level accumulation (resets on CLI exit)
- `--dry-run` uses estimates without API calls
- Budget guardrails at 80%/95%/100% thresholds

### FR-5: Shared Filter System

- `count` and `discover` share identical filter options via Click decorator/mixin
- All 12 positive filters + 7 negation filters available on both
- `phrase_match` documented as OR logic in help text
- `employee_range` validated as "min,max" format
- `category` validated against 46-item enum

### FR-6: CSV Export

- Standard columns: domain, name, score, similarity, employees, city, state, country, public_emails, social_urls, description
- Multi-value fields joined with semicolons
- Descriptions properly quoted (contain commas)
- Auto-naming: `{seed}-lookalikes-{YYYY-MM-DD}.csv`

### FR-7: Agent-Native Design

- SKILL.md at repo root with triggers and command reference
- CLAUDE.md at repo root with developer/agent instructions
- Predictable exit codes (0-6)
- JSON output includes `_meta` block with cost, cache status, timestamp
- stderr for progress, stdout for data (pipe-safe)

---

## Non-Goals

- **No REPL/interactive mode** -- CLI commands only. Workflows handle multi-step interaction.
- **No GUI** -- terminal output only (Rich tables for pretty printing).
- **No webhook support** -- this is a pull-based CLI, not a server.
- **No built-in scheduling** -- use cron or automation tools externally.
- **No MCP server mode** -- the existing MCP server handles that. This is the CLI complement.

---

## Technical Architecture

### Repository Structure

```
discolike-cli/
├── .github/
│   └── workflows/
│       └── ci.yml                    # Lint, typecheck, tests on PR
├── src/
│   └── discolike/
│       ├── __init__.py               # __version__
│       ├── cli.py                    # Click entry point, global options
│       ├── client.py                 # DiscoLikeClient -- httpx with retry
│       ├── config.py                 # Config loading (env > yaml)
│       ├── cost.py                   # CostTracker -- per-call + session totals
│       ├── cache.py                  # SQLite-backed local cache
│       ├── errors.py                 # Typed error hierarchy (exit codes 1-6)
│       ├── output.py                 # OutputManager -- JSON/table/CSV
│       ├── types.py                  # Pydantic models for all API shapes
│       ├── constants.py              # Pricing tables, categories, employee ranges
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── account.py            # status, usage
│       │   ├── discover.py           # discover, count (shared filters)
│       │   ├── enrich.py             # profile, score, growth
│       │   ├── extract.py            # extract-website-text
│       │   ├── contacts.py           # contacts search
│       │   ├── match.py              # name -> domain
│       │   ├── append.py             # bulk firmographic append
│       │   ├── vendors.py            # tech stack
│       │   ├── subsidiaries.py       # corporate hierarchy
│       │   ├── saved.py              # list + save exclusion lists
│       │   └── workflow.py           # composite workflow commands
│       └── exporters/
│           ├── __init__.py
│           ├── csv_export.py         # CSV with multi-value semicolons
│           └── json_export.py        # JSON/JSONL writer
├── tests/
│   ├── conftest.py                   # Shared fixtures, mock client
│   ├── test_client.py
│   ├── test_cost.py
│   ├── test_cache.py
│   ├── test_output.py
│   ├── test_config.py
│   ├── commands/
│   │   ├── test_account.py
│   │   ├── test_discover.py
│   │   ├── test_enrich.py
│   │   ├── test_extract.py
│   │   ├── test_saved.py
│   │   └── test_workflow.py
│   └── fixtures/                     # Sample API response JSONs
│       ├── account_status.json
│       ├── discover_results.json
│       ├── business_profile.json
│       └── ...
├── CLAUDE.md                         # Agent/developer instructions
├── SKILL.md                          # Agent discovery file
├── README.md
├── LICENSE                           # MIT
├── pyproject.toml                    # Build config, deps, entry point
└── .gitignore
```

### Dependencies

```toml
[project]
name = "discolike-cli"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "respx>=0.21",
    "ruff>=0.4",
    "mypy>=1.10",
]

[project.scripts]
discolike = "discolike.cli:cli"
```

### Command Tree Summary

```
discolike
├── config show|set|clear
├── account status|usage
├── extract <domain>
├── count [filters]
├── discover [filters] --max-records --output
├── profile <domain>
├── score <domain>
├── growth <domain>
├── contacts --domain --title --max-records
├── match <company-name>
├── append --input --fields --output
├── vendors <domain>
├── subsidiaries <domain>
├── saved list|save
├── workflow discover|enrich-list
├── costs [--reset]
└── Global: --json --csv --fields --quiet --no-cache --dry-run --version
```

### Key Design Decisions

1. **Python + Click** -- Standard for portable, pip-installable CLIs. Click over Typer for fine-grained control over shared filter decorators.
2. **httpx** -- Connection pooling, proper timeouts, native async. `respx` for clean mocking in tests.
3. **Pydantic v2** -- All API shapes as typed models. Validates responses, deterministic JSON output, IDE autocomplete.
4. **SQLite cache** -- Single file at `~/.discolike/cache.db`. Atomic operations, TTL queries, no file proliferation.
5. **Rich** -- Standard Python terminal output library. Colors, Unicode tables, proper width handling.
6. **Shared filter decorators** -- `count` and `discover` share 20+ options via a Click decorator mixin. Define once, apply to both.
7. **stderr for progress, stdout for data** -- `discolike discover --json | jq '.records'` works because progress never pollutes the data stream.

---

## Critical Reference Files

| File                                     | Purpose                                           |
| ---------------------------------------- | ------------------------------------------------- |
| `reference/discolike-field-reference.md` | Complete API fields, pricing, filters, categories |
| `reference/discolike-workflow.md`        | 8-step workflow process from existing skill       |
| `https://api.discolike.com/v1/docs/`     | Official REST API documentation                   |

---

## Verification Plan

### Build & Install

```bash
cd discolike-cli
pip install -e ".[dev]"
discolike --version
```

### Unit Tests

```bash
pytest tests/ -v --cov=discolike
ruff check src tests
mypy src
```

### Manual Smoke Tests

```bash
# Auth & config
export DISCOLIKE_API_KEY="dk_..."
discolike config show
discolike account status
discolike account usage

# Core commands
discolike extract leadgrow.ai
discolike count --domain leadgrow.ai --country US
discolike discover --domain leadgrow.ai --country US --max-records 5
discolike discover --domain leadgrow.ai --country US --max-records 5 --json
discolike profile leadgrow.ai
discolike score leadgrow.ai
discolike growth leadgrow.ai

# Cost tracking
discolike discover --domain leadgrow.ai --max-records 10 --dry-run
discolike costs

# Workflow
discolike workflow discover --seed leadgrow.ai --country US --max-records 25 --enrich-top 3 --output ./test-output.csv

# CSV export verification
cat ./test-output.csv | head -5

# Agent integration (JSON pipe)
discolike discover --domain leadgrow.ai --max-records 5 --json | python -c "import json,sys; d=json.load(sys.stdin); print(f'{d[\"count\"]} records, cost: ${d[\"_meta\"][\"cost\"][\"this_call\"]}')"
```

### CI Pipeline

```yaml
# .github/workflows/ci.yml
- ruff check (lint)
- mypy src (typecheck)
- pytest --cov (unit tests, no API key needed)
```
