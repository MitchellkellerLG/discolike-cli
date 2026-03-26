---
name: discolike-cli
description: >
  Standalone CLI for DiscoLike B2B company discovery API. Find lookalike companies,
  build prospect lists, enrich domains with firmographic data, track costs.
  Use when building prospect lists from seed domains, sizing markets, enriching
  domain lists, or automating discovery workflows in CI/CD pipelines.
triggers:
  - find companies like
  - build prospect list
  - ICP list
  - discover companies
  - discolike
  - lookalike companies
  - size the market
  - prospect list from seed
  - company discovery
  - enrich domains
  - firmographic data
  - digital footprint
  - discovery workflow
version: 0.1.0
maturity: built
---

# DiscoLike CLI

Standalone CLI for the DiscoLike B2B company discovery API (65M+ domains, 180+ countries).

## Install

```bash
pip install -e ".[dev]"
export DISCOLIKE_API_KEY="dk_..."
```

## Command Reference

```
discolike
├── config show|set|clear         # API key and settings
├── account status|usage          # Plan, spend, budget
├── extract <domain>              # Cached website text
├── count [filters]               # Count matching domains
├── discover [filters]            # Find similar companies
├── profile <domain>              # Business profile enrichment
├── score <domain>                # Digital footprint score
├── growth <domain>               # Growth metrics
├── contacts --domain <d>         # B2B contacts (Team+)
├── match <company-name>          # Name to domain (Team+)
├── append --input --fields -o    # Bulk firmographic append
├── vendors <domain>              # Tech stack (Team+)
├── subsidiaries <domain>         # Corporate hierarchy (Enterprise)
├── saved list|save               # Exclusion lists
├── workflow discover|enrich-list # Composite workflows
├── costs [--reset]               # Session cost tracking
└── Global: --json --csv --fields --quiet --no-cache --dry-run
```

## Key Patterns

- **Dual output:** TTY = Rich tables, pipe = JSON. `--json` forces JSON.
- **Cost on every call:** Footer in table mode, `_meta.cost` in JSON mode.
- **Exit codes:** 0=success, 1=API, 2=auth, 3=rate limit, 4=plan gate, 5=budget, 6=validation.
- **stderr for progress, stdout for data.** Pipe-safe.
- **--dry-run** shows estimated cost without API calls.

## Workflow Example

```bash
discolike workflow discover \
  --seed leadgrow.ai \
  --country US \
  --max-records 100 \
  --enrich-top 5 \
  --output prospects.csv \
  --no-confirm
```
