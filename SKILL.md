---
name: discolike-discovery
description: >
  End-to-end account list building using DiscoLike CLI. From seed domain or ICP
  description through validated, normalized prospect lists ready for Clay enrichment.
  Includes validation loop, market mapping, and campaign brief integration.
  Use when building prospect lists, finding lookalike companies, sizing a market,
  or sourcing target accounts for outbound campaigns.
cli: discolike
triggers:
  - find companies like
  - build prospect list
  - build account list
  - ICP list
  - discover companies
  - market discovery
  - find lookalikes
  - discolike
  - lookalike companies
  - size the market
  - prospect list from seed
  - company discovery
  - TAM sizing
  - target account list
  - source accounts
version: 2.0.0
maturity: built
feedback:
  last_reviewed: 2026-04-09
  known_gaps:
    - campaign brief system not yet built (document integration point only)
    - Clay table template for account lists not yet standardized in this skill
---

# DiscoLike Account List Builder

End-to-end account sourcing workflow. From a seed domain or ICP description to a validated, normalized prospect list ready for Clay enrichment and outbound campaigns.

**This skill is CLI-first.** All DiscoLike operations use the `discolike` CLI (installed via `pip install -e discolike-cli/`). The CLI handles cost tracking, caching (90-day extract, 7-day profiles), budget guardrails, and output formatting automatically.

## Core Rules (Non-Negotiable)

These four rules were learned the hard way. Violating any of them produces bad lists while feeling productive. Read them before touching any phase.

### Rule 1: Semantic overlap trap — never phrase-negate target language

**Target ICP language overlaps with noise language because they serve the same persona.** If you're building a list of marketing SaaS (products sold to marketers), the targets will have "marketing" all over their sites because they talk to marketers. Negate "marketing" and you kill your targets along with the agencies.

The pattern is universal:
- Marketing SaaS targets mention "marketing" (sell to marketers)
- Carbon accounting SaaS targets mention "sustainability consulting" (sell to sustainability teams)
- HR tech targets mention "recruitment" (sell to recruiters)
- Sales enablement SaaS targets mention "outbound" and "SDRs" (sell to sales ops)
- Legal tech targets mention "legal services" (sell to law firms)

The target and the noise share vocabulary because they exist in the same market. Keyword exclusion cannot distinguish "a marketing agency" from "a SaaS that sells to marketing agencies."

**Before proposing any `--negate-phrase`, ask: could a target company's homepage contain this word in a legitimate context? If yes, the exclusion is too broad.** Use semantic classification (DiscoGen or validate) instead — it discriminates by business model, not vocabulary.

**Safe exclusion hierarchy (most safe → least safe):**
1. Domain-level exclusions (exact match, zero overlap risk)
2. Category-level exclusions (NLP-classified, smarter than keywords)
3. Semantic qualification via DiscoGen/validate (the right tool for most exclusions)
4. Phrase exclusions (only when the phrase has zero possible target overlap — rare)

### Rule 2: Inclusion-first — let the data surface the problem

Start every discovery run with positive filters only. No `--negate-phrase`, no `--negate-icp-text`, no `--negate-domain` in the first call. Pull 50 records. Analyze what's actually noise. THEN apply targeted exclusions based on what you observed.

The reason: upfront exclusions are guesses about what will be wrong. They often kill good results silently (a commercial EPC that mentions "residential" once gets dropped). The data itself is a better feedback signal than your priors.

**Autonomous exclusion loop (Phase 4):**

1. **Round 0:** Inclusion-only filters. Pull 50 records. No negations.
2. **Data conversation (up to 4 autonomous iterations):**
   - Analyze batch. Identify dominant noise pattern.
   - Propose ONE targeted exclusion OR ONE semantic classification question as a hypothesis.
   - Re-run discover (or run DiscoGen for classification).
   - Verify the problem is reduced. If yes, lock in that action.
   - If the problem shifted, propose the next hypothesis.
3. **Cap at 4 iterations.** Terminate early if fit rate is at target or diminishing returns hit.
4. **Report to user** with final batch + iteration trail summary. User decides whether to proceed to full pull.

**One prompt per round, one action per round.** Don't try to do multiple things per iteration — it makes the feedback signal muddy.

Each iteration costs ~$0.22 for discover 50. Four iterations = ~$1. Cheap compared to the cost of bad upfront exclusions killing good results.

### Rule 3: Capital signal, not size — don't tight-filter on employees

Employee count is a bad proxy for outbound fit. A 15-person Series A startup with $10M raised is a better outbound buyer than a 100-person bootstrapped consulting firm. We care about capital, not headcount.

Three reasons:
1. **DiscoLike's employee data is weak for small companies** (buckets are coarse, often stale, frequently missing).
2. **Capital ≠ size.** Funded startups and manufacturers with working capital are real buyers regardless of headcount.
3. **Tight filters exclude ideal targets** (well-funded 20-person startups, 40-person commercial EPCs with project financing).

**Use `--employees "1,1500"` as a loose upper cap** (only excludes massive enterprises). Don't set a minimum. Push capital qualification DOWNSTREAM to Clay enrichment where funding data actually lives (Crunchbase, PitchBook, company filings).

**Also important:** don't pre-filter by business model. Consultants with direct B2B sales motions ARE valid targets. Manufacturers with direct commercial sales ARE valid targets. The real filter is "direct B2B motion vs channel/distributor" — answered by DiscoGen during validation, not by upfront assumptions about "SaaS is our sweet spot."

### Rule 4: Realistic benchmarks — 60-70% is the target, not 80%

| Fit rate | Interpretation |
|---|---|
| 60-70% strong fit | **Normal outcome. Proceed.** |
| >70% | Unusually clean list. Usually means inclusions are very tight. |
| 40-60% | Needs refinement. Run another iteration. |
| <40% | Rework ICP from Phase 1. Prompt is likely wrong. |

Perfect lists are rare. A 60% strong fit rate with precise semantic classification beats an 85% fit rate that killed ideal targets via overbroad exclusions.

## When to Invoke

- Any time we need to build a target account list and the user hasn't provided one
- Finding lookalike companies for an existing client or seed domain
- Sizing a market before committing to outbound
- Sourcing accounts for a new campaign brief

## When NOT to Invoke

- User already has a domain list (skip to data-prep or list-building-pipeline)
- Single company lookup (use `discolike profile <domain>` directly)
- Contact-level enrichment only (use list-building-pipeline downstream)

## Prerequisites

- `discolike` CLI installed and configured (`discolike config show` to verify)
- `DISCOLIKE_API_KEY` set in environment

---

## Phase 1: Input & Context Gathering

### If user provides a seed domain:

Ask targeted questions to build filter parameters. Don't proceed until you understand:

| Parameter | Question | Why It Matters |
|---|---|---|
| **Geography** | Which countries/regions? | Filters 65M domains down to relevant markets |
| **Company size** | Employee range? Revenue indicators? | Prevents enterprise/SMB mismatch |
| **Industry/vertical** | What space are they in? Adjacent spaces? | Category filters + phrase match terms |
| **Exclusions** | What types of companies are a hard NO? | Negation filters save budget on bad results |
| **Tech stack** | Any tech requirements on target sites? | Requires Team+ plan; flag if on Starter |

### If user has NO seed domain:

Gather enough context to build an ICP description:

1. What does the ideal target company do? (business model, service/product)
2. Who do they sell to? (their customers)
3. What words would appear on their website? (phrase match candidates)
4. Size, geo, and exclusions (same as above)

Use this context to craft `--icp-text` and `--phrase` parameters directly.

### Check account status first:

```bash
discolike account status
```

Note the plan (Starter/Pro/Team/etc.), MTD spend, and remaining budget. Report to user. If budget is tight, flag it before proceeding.

**Plan-gated features to watch for:**
- Starter: No vendors (tech stack), no contacts, no match
- Pro: Adds market segmentation
- Team+: Adds vendors, contacts, match

---

## Phase 2: Market Sizing

Run two things in parallel:

### 2a. DiscoLike count (ground truth for filter accuracy)

```bash
discolike count --domain example.com --country US --category SAAS --employees "50,500"
```

This tells you how many domains match YOUR FILTERS. If the count is low, your filters may be too tight, not the market too small.

- **< 50 matches:** Filters are too tight. Loosen before proceeding.
- **50-5,000:** Good range for discovery.
- **> 10,000:** Tighten filters for relevance.

### 2b. Independent market size estimate (subagent)

Spawn a subagent to estimate the realistic TAM independently of DiscoLike's filters. The subagent uses the ICP parameters (industry, size, geo, business model) and web research to estimate how many companies should exist in this market.

**Compare the two numbers:**

| DiscoLike Count | Independent Estimate | Interpretation |
|---|---|---|
| 200 | 2,000+ | Filters are too tight. Phrase match or category is excluding good fits. |
| 200 | ~200-300 | Filters are well-calibrated. Proceed. |
| 5,000 | ~500 | Filters are too loose. Tighten category or add phrase match. |

This comparison is the early warning system. Without it, you'd see "200 matches" and not know if that's 100% of the market or 10%.

---

## Phase 3: ICP & Discovery

Two paths depending on speed vs control:

### Fast path (recommended for first pass):

```bash
discolike discover \
  --domain example.com \
  --auto-icp \
  --auto-phrases \
  --country US \
  --employees "50,500" \
  --max-records 50 \
  -o temp/csv-staging/discovery-validation.csv
```

DiscoLike scrapes the seed domain and generates ICP text + phrases automatically. Good for a quick validation batch.

### Precision path (when fast path results are off):

```bash
# Step 1: Extract website text
discolike extract example.com

# Step 2: Read the output, craft a tight ICP description
# Step 3: Run discover with manual ICP + phrases
discolike discover \
  --domain example.com \
  --icp-text "B2B outbound lead generation agency using cold email for SaaS companies" \
  --phrase "cold email" \
  --phrase "outbound" \
  --country US \
  --employees "50,500" \
  --negate-category FINANCIAL_SERVICES \
  --negate-phrase "recruitment" \
  --max-records 50 \
  -o temp/csv-staging/discovery-validation.csv
```

### Cost check before committing:

```bash
discolike --dry-run discover --domain example.com --auto-icp --country US --max-records 50
```

Shows estimated cost without hitting the API.

---

## Phase 4: Validation Loop

**This is the core quality gate. Do not skip.**

### 4a. ICP validation (structured scoring)

Run the 50-company batch through DiscoLike's validate endpoint:

```bash
discolike validate \
  --icp "B2B outbound lead generation agency using cold email for SaaS companies" \
  --input temp/csv-staging/discovery-validation.csv \
  --context-mode website \
  --yes
```

Returns per-domain: **Fit** (yes/partial/no), **Confidence** (high/medium/low), **Reasoning**.

### 4b. Custom qualification (optional, powerful)

Use DiscoGen to run specific qualification questions against the batch:

```bash
discolike discogen run \
  --prompt "Does this company actively sell outbound lead generation services? Answer yes/no with one sentence of evidence." \
  --input temp/csv-staging/discovery-validation.csv \
  --context-mode website \
  --yes
```

This catches companies that technically match the ICP text but aren't actually in the business you're targeting.

### 4c. Present results to user

Show the validation results with clear recommendations:

- **Strong fits** (yes + high confidence) — these validate the ICP prompt is working
- **Partial fits** — analyze why. Are filters too loose, or are these adjacent companies worth including?
- **Bad fits** (no + high confidence) — these tell you what to negate

**Suggest next steps:**
- If >70% strong fit: ICP is solid. Ready to proceed.
- If 40-70% strong fit: Refine. Add negation filters, adjust phrases, tighten category.
- If <40% strong fit: ICP needs rework. Go back to Phase 3 precision path.

### 4d. Iterate

User and model go back and forth. Each iteration:

1. Adjust filters based on feedback (add `--negate-domain`, `--negate-category`, adjust `--phrase`)
2. Re-run discover with updated params (50 records)
3. Re-run validate
4. Present updated results

**Only proceed to full pull when the user explicitly approves.**

### 4e. Phase 4 iteration patterns — two levers and when to use each

After calibration rounds surface noise, two tools exist. Use them in this order:

**Lever 1: Domain exclusions** (`--negate-domain`)
Removes specific noise domains AND their embedding neighbors. Domains with high scores + wrong category are gravity wells — they pull semantically similar companies toward them. Excluding a trade association or a resi platform removes not just that domain but the cluster it anchors.

- Start here in round 1 refinement
- Target: high-score wrong-category domains (score >200 + clear noise type)
- Prioritize: national nonprofits, trade associations, resi consumer platforms, hardware OEMs, media orgs
- Cap: 10 entries max per CLI call

**Lever 2: Seed addition** (adding `--domain` entries)
Shifts the embedding center toward the target archetype. More powerful than exclusions once obvious noise is cleared, because it pulls toward good rather than pushing away from bad.

- Use after exclusions have cleared the clearest noise categories
- Add 1-3 strong-fit domains from your calibration results as additional seeds
- Effect is amplified: a new seed repositions the entire query vector, not just removes one data point

**Decision rule:**
1. Round 0: inclusion-only, pull 50
2. Round 1: analyze noise. Apply exclusions (lever 1) targeting top noise categories
3. Round 2: apply 1-2 additional seed domains (lever 2) if round 1 didn't fully resolve the issue
4. Calibration pull (200 records) before committing to full 500

### 4f. Calibration pull before full pull

Always run a 200-record validation pull before the full pull. The 50-record calibration only validates the top of the result curve. Quality at rank 200 can be significantly lower than quality at rank 10 in dense embedding neighborhoods.

```bash
discolike discover \
  [all flags] \
  --max-records 200 \
  -o temp/csv-staging/discovery-calibration-200.csv
```

**Spot-check three bands:** ranks 1-10, 90-100, 190-200. Classify each as strong fit / marginal / noise. If >=45% strong fit across all three bands: proceed to full pull. If below threshold: do ONE more exclusion swap (identify 3 least-impactful exclusions, replace with 3 new ones from observed noise), re-run 200-record pull, re-check.

**Cap at one swap.** If you still can't clear 45%, you've hit the natural plateau for this embedding neighborhood. Proceed anyway and document the residual noise rate.

### 4g. Score decay reality

Score curves in DiscoLike decay logarithmically. Top-50 quality does NOT predict full-500 quality.

| Rank band | Typical strong-fit rate |
|---|---|
| 1-50 | 55-70% |
| 51-150 | 45-55% |
| 150-300 | 35-45% |
| 300-500 | 25-40% |

**~15% quality degradation from rank 50 to rank 500 is normal in dense neighborhoods.** This is the embedding gravity effect — as you move further from the seed centroid, companies are present because they share general industry vocabulary, not because they match the specific ICP.

**Management tools:** calibration pulls + domain exclusions reduce decay but don't eliminate it. Don't use min-score filtering as a lever — it removes companies based on domain age/footprint size, not on ICP fit. A 15-person funded C&I developer will score low but be a perfect target.

**The right response to quality decay:** document in the brief, set Clay qualification filters to compensate downstream, or use DiscoGen to do per-domain fit classification before outreach.

---

## Phase 5: Full Pull & Market Mapping

Once validated, pull the full list. Phase 5 has two modes: **standard pull** (up to ~1K records in one call) and **graduated scale** (2K–10K via multi-round market mapping). Choose based on the market size estimate from Phase 2.

### Standard pull (up to ~1K records)

```bash
discolike discover \
  --domain example.com \
  --icp-text "..." \
  --phrase "..." \
  --country US \
  --employees "50,500" \
  --max-records 500 \
  --save-exclusion \
  -o temp/csv-staging/discovery-round-1.csv
```

Always include `--save-exclusion` — it saves this round's results as an exclusion list for deduplication in subsequent rounds.

---

### Graduated scale: 2K → 10K with user approval gates

For markets where the Phase 2 estimate supports >1K targets, use a tiered graduation ladder. **Each tier requires explicit user approval and a cost preview before running.**

The architecture is multi-round market mapping, NOT a single large `--max-records` call. This is intentional:
- API stability at very high record counts is unverified
- Multi-round allows re-seeding with strong fits between rounds, improving quality at depth
- `--exclude` deduplicates cleanly across rounds using saved query IDs

#### Chunk size

Chunk size is flexible — use 500 or 1000 records per round depending on the situation:

| Chunk size | When to use |
|------------|-------------|
| 500        | First pull of a new ICP, uncertain quality at depth, tight budget |
| 1000       | Calibration is locked, quality has been proven at the 200-record gate, want faster coverage |

Pick chunk size before committing to a tier. It determines round count and cost per round (~$1.75/500-record round, ~$3.50/1000-record round).

#### Tier structure

| Tier | Records | Rounds (500-chunk) | Rounds (1000-chunk) | Est. Cost |
|------|---------|--------------------|--------------------|-----------|
| S    | 500     | 1                  | 1                  | ~$2–3.50  |
| M    | 2,000   | 4                  | 2                  | ~$7       |
| L    | 5,000   | 10                 | 5                  | ~$16      |
| XL   | 10,000  | 20                 | 10                 | ~$32      |

Costs are estimates. Always run `--dry-run` per round and sum before committing.

#### Graduation flow

**Before each tier:** Show the user the cost estimate, round count, and chunk size. Do not proceed without explicit "yes" from the user.

```
Tier M (2,000 records): chunk size 1000 → 2 rounds × ~$3.50/round = ~$7 total.
Current config: [seeds, categories, geo, exclusions].
Proceed?
```

**Round-by-round execution:**

```bash
# Round 1: base pull with --save-exclusion
discolike discover \
  [all calibrated flags] \
  --max-records 1000 \        # or 500 — set chunk size here
  --save-exclusion \
  -o temp/csv-staging/discovery-r1.csv

# Get saved query ID
discolike saved list

# Round 2: exclude round 1, add strong-fit seeds from round 1
discolike discover \
  --domain original-seed.com strong-fit-from-r1.com strong-fit-2.com \
  [all other calibrated flags] \
  --exclude <query-id-r1> \
  --max-records 1000 \        # same chunk size as round 1
  --save-exclusion \
  -o temp/csv-staging/discovery-r2.csv

# Round 3: exclude all prior rounds
discolike discover \
  [all calibrated flags] \
  --exclude <query-id-r1> --exclude <query-id-r2> \
  --max-records 1000 \
  --save-exclusion \
  -o temp/csv-staging/discovery-r3.csv

# Continue pattern until tier record count is reached
```

**Seeding between rounds:** After each round, identify 1-2 strong-fit domains from the new results. Add them as `--domain` seeds in the next round. This re-centers the embedding toward the target archetype as you go deeper into the market.

**Diminishing returns check (quality gate between tiers):**

After each full tier completes, spot-check the LAST round's output (ranks 1-10 and 40-50 of that round). If strong-fit rate drops below 30%, you've exhausted the addressable market — stop and report to user rather than continuing to the next tier.

```
Round 4 quality check: 4/10 strong fit at ranks 40-50 (40%).
Still above 30% floor. Proceeding to tier M completion.

Round 8 quality check: 2/10 strong fit at ranks 40-50 (20%).
Below 30% floor — market likely saturated at this ICP. Stopping.
Total unique records: 3,847. Recommend treating this as your full TAM.
```

**Combine rounds into final file:**

```python
import csv, glob

all_rows = []
seen = set()
for f in sorted(glob.glob('temp/csv-staging/discovery-r*.csv')):
    with open(f, 'r', encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            domain = row['domain'].lower().lstrip('www.')
            if domain not in seen:
                seen.add(domain)
                all_rows.append(row)

with open('temp/csv-staging/discovery-final.csv', 'w', newline='') as fh:
    writer = csv.DictWriter(fh, fieldnames=all_rows[0].keys())
    writer.writeheader()
    writer.writerows(all_rows)

print(f"Total unique: {len(all_rows)}")
```

---

### Enrich the final list

```bash
discolike workflow enrich-list \
  --input temp/csv-staging/discovery-final.csv \
  --output temp/csv-staging/discovery-enriched.csv \
  --fields profile,score,growth
```

Growth metrics flag companies that are expanding (higher outbound receptivity). Score flags dead/parked domains to exclude before downstream processing.

---

## Phase 6: Post-Processing Handoff

The enriched CSV is NOT campaign-ready. Hand off to the data pipeline:

### Step 0: CSV normalization (do this before data-prep or Clay)

DiscoLike CSVs require manual normalization before any downstream tool can consume them reliably.

**Critical: always parse with Python, not shell tools.** The `description` field uses internal commas and is inconsistently quoted. Shell tools like `cut`, `awk`, and spreadsheet imports break on this. Use Python's `csv` module or pandas:

```python
import csv
rows = []
with open('temp/csv-staging/discovery-final.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)
```

**Normalization operations to run before Clay:**

| Field | Raw format | Normalized output |
|---|---|---|
| `employee_range` | `"11-50"` string | Split into `employees_min` (int) and `employees_max` (int) |
| `public_emails` | `"a@co.com; b@co.com"` | Split into `email_1`, `email_2` columns |
| `social_urls` | `"https://linkedin.com/...; https://twitter.com/..."` | Parse into `linkedin_url`, `twitter_url` per-platform columns |
| `domain` | `"www.example.com"` | Strip `www.`, lowercase — canonical form for Clay dedup |
| `name` | raw | Keep as-is for Clay `Company Name` column |

**Employee range split example:**

```python
def split_employees(emp_str):
    if not emp_str or '-' not in emp_str:
        return None, None
    parts = emp_str.split('-')
    try:
        return int(parts[0]), int(parts[1].replace('+', ''))
    except ValueError:
        return None, None

for row in rows:
    row['employees_min'], row['employees_max'] = split_employees(row.get('employees', ''))
```

**Social URL parser example:**

```python
def parse_socials(social_str):
    linkedin, twitter = '', ''
    if not social_str:
        return linkedin, twitter
    for url in social_str.split(';'):
        url = url.strip()
        if 'linkedin.com' in url:
            linkedin = url
        elif 'twitter.com' in url or 'x.com' in url:
            twitter = url
    return linkedin, twitter
```

**Clay field mapping (standard column names Clay expects):**

| Normalized column | Clay column name |
|---|---|
| `name` | Company Name |
| `domain` | Domain |
| `description` | Description |
| `employees_min` | Employees Min (for headcount range filter) |
| `employees_max` | Employees Max |
| `linkedin_url` | LinkedIn URL |
| `city` | City |
| `state` | State |
| `country` | Country |

### Step 1: CSV normalization (data-prep skill)

```
/data:data-prep
```

Key steps the data-prep skill handles:
- Domain health checks (HTTP alive + MX records)
- MX provider segmentation (Google Workspace vs O365 vs other)
- Column normalization and dedup
- Title filtering and tenure segmentation (if contact data present)
- TechSight enrichment (free tech stack detection)

### Step 2: Clay table graduation

Push the normalized CSV to Clay for gap-filling enrichment:

```
/data:clay-table-setup
```

Clay handles: missing firmographic data, contact discovery, email verification, and any custom enrichment columns defined in the table template.

### Step 3: Full enrichment pipeline (if needed)

For contact-level enrichment after Clay:

```
/data:list-building-pipeline --input normalized.csv --domain-col domain
```

Pipeline: AI Ark two-tier search → waterfall email validation → sendable CSV.

---

## Campaign Brief Integration

**Account list building should always be part of a campaign brief.**

### Reading from a brief

If a campaign brief exists, load it first. The brief contains:
- ICP definition (use as `--icp-text` input)
- Target geography and size parameters
- Poke-the-bear questions (use for DiscoGen qualification prompts)
- Exclusions and past campaign learnings

### Writing back to a brief

After completing account sourcing, document in the campaign brief:
- Discovery parameters used (filters, ICP text, phrases)
- Validation results (fit rates, refinement iterations)
- Market size estimate vs actual results
- Final list stats (domain count, geo breakdown, size distribution)
- Session ID for this Claude Code session
- Any issues or learnings for future improvement

### Session tracking

Always record the Claude Code session ID in the brief. This enables:
- Post-mortem analysis if results underperform
- Pattern extraction across campaigns
- Friction logging for skill improvement

---

## Cost Reference

**CLI tracks costs automatically.** Check running total anytime:

```bash
discolike costs
```

### Starter Plan (current)

| Component | Cost |
|---|---|
| Per query | $0.18 |
| Per 1,000 records | $3.50 |

### Typical workflow costs

| Workflow | API Calls | Est. Cost |
|---|---|---|
| Validation round (count + discover 50 + validate) | 3 | ~$1.50 |
| Full pull (500 records + enrich) | 3-4 | ~$3.00 |
| Full workflow with 2 refinement rounds | 8-10 | ~$5.00 |
| Market mapping (3 rounds of 500) | 12-15 | ~$10.00 |

**Budget guardrails are automatic:** warnings at 80%/95% of monthly budget, hard block at 100%.

Use `--dry-run` on any command to preview cost without API calls.

---

## Filter Quick Reference

### Positive filters (narrow results)

| Flag | Example |
|---|---|
| `--domain` | `--domain example.com --domain seed2.com` |
| `--icp-text` | `--icp-text "B2B outbound agency for SaaS"` |
| `--phrase` | `--phrase "cold email" --phrase "outbound"` (OR logic) |
| `--country` | `--country US --country GB` |
| `--state` | `--state CA` |
| `--employees` | `--employees "50,500"` |
| `--category` | `--category SAAS` |
| `--min-score` | `--min-score 100` (filter out dead/parked domains) |
| `--auto-icp` | Auto-generate ICP from seed |
| `--auto-phrases` | Auto-generate phrases from ICP |
| `--enhanced` | AI-powered result enhancement |
| `--variance` | `LOW` to `UNRESTRICTED` (result diversity) |
| `--consensus` | `1-20` (search vector strictness) |

### Negation filters (exclude results)

| Flag | Example |
|---|---|
| `--negate-domain` | `--negate-domain bad-fit.com` |
| `--negate-category` | `--negate-category FINANCIAL_SERVICES` |
| `--negate-phrase` | `--negate-phrase "recruitment"` |
| `--negate-country` | `--negate-country CN` |
| `--negate-icp-text` | `--negate-icp-text "enterprise consulting"` |

### Industry categories

Run `discolike discover --help` for the full list. Common ones:
`SAAS`, `ADVERTISING_AND_MARKETING`, `IT_SERVICES`, `SOFTWARE`, `E-COMMERCE`, `HEALTHCARE`, `FINANCIAL_SERVICES`, `CYBERSECURITY`, `EDUCATION`

### Employee range buckets

`1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+`

Filter format: `"min,max"` e.g. `"50,500"` matches `51-200` and `201-500` buckets.

---

## Key Behaviors

1. **Never discover without understanding the ICP first.** Gather size, geo, type, and exclusions before any API call.
2. **Validate before scaling.** 50-company validation round with structured scoring. No full pulls on untested filters.
3. **User approves before full pull.** The validation loop is interactive. Only proceed when explicitly told to.
4. **Compare count vs independent estimate.** This catches filter miscalibration early.
5. **Use exclusions for market mapping.** Save each round, exclude from the next. Covers the full TAM.
6. **CLI-first, MCP-fallback.** The CLI handles cost tracking, caching, and output. Use MCP tools only for edge cases.
7. **Track costs.** Report running total after each step. Use `--dry-run` before expensive calls.
8. **Document everything in the campaign brief.** Parameters, results, session IDs, learnings.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Jumping to discover without gathering ICP context | Complete Phase 1 first. Every filter parameter matters. |
| Trusting count as market size | Count reflects filter accuracy, not real TAM. Use independent estimate. |
| Skipping validation, pulling 500+ records immediately | Always do 50-company validation round first. |
| Running multiple exploratory discovers to "see what's out there" | Use `--auto-icp` for a quick first pass, then refine. One call, not five. |
| Not saving exclusion lists between rounds | Always `--save-exclusion` on full pulls for market mapping. |
| Manually enriching one-by-one with profile | Use `workflow enrich-list` for batch enrichment. |
| Assuming phrase_match is AND | It's OR. `["cold email", "outbound"]` = EITHER term. |
| Ignoring plan gates | Check plan in Phase 1. Vendors/contacts/match need Team+. |

## Downstream Integration

| Direction | Skill | Purpose |
|---|---|---|
| Upstream | campaign brief | ICP definition, target params, poke-the-bear questions |
| Upstream | situation-miner | Buying situations for ICP refinement |
| Upstream | offer-clarity-workshop | Target persona definitions |
| **Downstream** | **data-prep** | **CSV normalization, domain health, MX checks** |
| **Downstream** | **clay-table-setup** | **Gap-filling enrichment in Clay** |
| Downstream | list-building-pipeline | Full contact enrichment (AI Ark + waterfall) |
| Downstream | cold-email-v2 | Write outreach for discovered companies |

---

## Known Limits & Upgrade Backlog

Issues discovered in production. Fix in CLI or document workaround before acting surprised again.

**1. `--negate-domain` cap is 10 entries**
CLI accepts more than 10 but the API silently caps at 10. CLI should validate client-side and error before the API call. Workaround: if you need more than 10 exclusions, prioritize the highest-score noise domains (strongest embedding gravity), not the most recently seen.

**2. Account status requires reading three spend fields together**
`month_to_date_spend`, `max_spend`, and `total_available_spend` are all needed to understand true budget position. Reading only one field gives a misleading picture (carryover credits make `max_spend` look like the ceiling when real budget may be double). Always check `account status` before any non-trivial pull.

**3. 50% strong-fit is the natural plateau in dense semantic neighborhoods**
In markets with heavy vocabulary overlap between targets and noise (solar + residential + commercial + nonprofit all share the same language), the embedding space can't distinguish them. Attempting to push past 50% with more exclusions will start removing good targets. When you hit 45-50% at depth, lock the config and document the residual noise rate. The right fix is downstream qualification (DiscoGen or Clay filters), not more exclusions.

**4. Seeds are more powerful than exclusions for escaping embedding gravity wells**
Domain exclusions remove single nodes. New seed domains shift the entire query centroid. If exclusions haven't resolved quality degradation after 2 rounds, add 1-2 strong-fit seeds from your calibration results rather than swapping more exclusions. One well-chosen seed domain often does more than 3 additional exclusions.
