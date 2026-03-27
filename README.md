# discolike-cli

Standalone CLI for the DiscoLike B2B company discovery API. 65M+ domains, 180+ countries, pip-installable.

## Install

```bash
pip install -e ".[dev]"
export DISCOLIKE_API_KEY="dk_..."
discolike --version
```

See **[SETUP.md](SETUP.md)** for the full setup walkthrough (prerequisites, config options, first commands, troubleshooting).

## Quick Start

```bash
# Check account
discolike account status

# Find companies like yours
discolike discover --domain example.com --country US --max-records 10

# Count the market
discolike count --domain example.com --country US --category SAAS

# Get a company profile
discolike profile example.com

# Full discovery workflow
discolike workflow discover --seed example.com --country US --max-records 100 --output prospects.csv
```

## Commands

| Command | Description |
|---------|-------------|
| `config show\|set\|clear` | API key and settings management |
| `account status\|usage` | Plan, spend, and budget info |
| `extract <domain>` | Extract cached website text |
| `count [filters]` | Count matching domains |
| `discover [filters]` | Find similar companies |
| `profile <domain>` | Business profile enrichment |
| `score <domain>` | Digital footprint score (0-999) |
| `growth <domain>` | Growth metrics and trends |
| `contacts --domain <d>` | B2B contacts search (Team+) |
| `match <name>` | Company name to domain (Team+) |
| `append --input --fields -o` | Bulk firmographic append |
| `vendors <domain>` | Tech stack data (Team+) |
| `subsidiaries <domain>` | Corporate hierarchy (Enterprise) |
| `saved list\|save` | Manage exclusion lists |
| `workflow discover\|enrich-list` | Composite workflows |
| `costs [--reset]` | Session cost breakdown |

## Discovery Search Vectors

Three ways to find companies, best used together:

**Domain similarity** (`--domain`) — Vector search on digital fingerprint. "Find companies that look like this one."

**ICP text** (`--icp-text`) — Semantic search on business model. "Find companies that do this."

**Phrase match** (`--phrase`) — Exact homepage text match. "Find companies that say this on their site." OR logic between phrases.

### Auto-ICP: Let DiscoLike Write Your ICP

The `--auto-icp` flag tells DiscoLike to extract your seed domain's website text and auto-generate an ICP description. Combines with domain similarity for tighter results without manual ICP crafting.

```bash
# Auto-generated ICP from seed domain
discolike discover --domain leadgrow.ai --auto-icp --country US --max-records 25

# Add auto phrase generation too
discolike discover --domain leadgrow.ai --auto-icp --auto-phrases --country US --max-records 25
```

For maximum precision, extract first and write your own ICP:

```bash
discolike extract leadgrow.ai
# Read the output, then craft a tight description:
discolike discover \
  --domain leadgrow.ai \
  --icp-text "B2B outbound lead generation agency using cold email for SaaS" \
  --phrase "cold email" \
  --country US \
  --max-records 25
```

### Narrowing Results

`discover` and `count` share 27 filter options:

| Filter | Example |
|--------|---------|
| `--country` | `--country US --country GB` |
| `--state` | `--state CA` |
| `--employees` | `--employees "50,500"` |
| `--category` | `--category SAAS` |
| `--min-score` / `--max-score` | `--min-score 100` |
| `--phrase` | `--phrase "cold email"` |
| `--negate-phrase` | `--negate-phrase "recruitment"` |
| `--negate-category` | `--negate-category FINANCIAL_SERVICES` |
| `--negate-country` | `--negate-country CN` |

Run `discolike discover --help` for the full list.

## Cost Protection

DiscoLike charges per query ($0.18) + per record returned. You only pay for records you pull, not records that exist.

**Built-in safeguards:**

1. **`count` first** — $0.18, zero records. See the universe size before committing.
2. **`--dry-run`** — Estimate cost without hitting the API.
3. **`--max-records`** — Hard cap on records returned (default: 10).
4. **Budget guardrails** — Warnings at 80%/95%, hard block at 100% of monthly budget.
5. **`workflow discover`** — Runs count, then 10-record validation, then asks for confirmation before the full pull.

```bash
# Check universe size ($0.18, no records)
discolike count --domain example.com --country US --category SAAS

# Preview cost without API call
discolike --dry-run discover --domain example.com --max-records 1000

# Safe workflow: count -> validate -> confirm -> full pull
discolike workflow discover --seed example.com --country US --max-records 100
```

## Global Options

| Flag | Effect |
|------|--------|
| `--json` | Force JSON output |
| `--csv` | Force CSV output |
| `--fields` | Filter output columns |
| `--quiet` | Suppress progress messages |
| `--no-cache` | Bypass local cache |
| `--dry-run` | Estimate cost without API calls |

## Output Modes

- **Terminal (TTY):** Rich tables with colors
- **Pipe/redirect:** JSON (auto-detected)
- **`--json`:** Force JSON with `_meta.cost` block
- **`--csv`:** Force CSV output

Progress and warnings always go to stderr.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | API error |
| 2 | Auth error (missing/invalid key) |
| 3 | Rate limited |
| 4 | Plan gate (feature requires upgrade) |
| 5 | Budget exceeded |
| 6 | Validation error |

## Development

```bash
pytest tests/ -v --cov=discolike    # Tests
ruff check src tests                 # Lint
mypy src                             # Type check
```

## License

MIT
