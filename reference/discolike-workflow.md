---
name: discolike-discovery
description: >
  Build targeted ICP prospect lists using DiscoLike's vector search and phrase
  matching. Combines semantic search with exact phrase matching for precision
  targeting. Use when building prospect lists from seed domains, finding
  lookalike companies, sizing a market before outbound, or refining lists
  with precision filters.
mcp: DiscoLike
triggers:
  - find companies like
  - build prospect list
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
version: 1.0.0
maturity: validated
feedback:
  last_reviewed: 2026-03-25
  known_gaps: []
---

# DiscoLike ICP List Builder

Build precision prospect lists by combining vector search (meaning) with phrase matching (exactness). This is the engineering approach to list building — index once, query in seconds.

## When to Use

- Building a prospect list from a seed domain or ICP description
- Finding lookalike companies for an existing client
- Sizing a market before committing to outbound
- Refining an existing list with precision filters

## When NOT to Use

- Quick single-company lookup (use `business-profile` directly)
- Need contact-level data (use waterfall-enrich downstream)
- Need tech stack filtering (requires TEAM plan)

## Prerequisites

- DiscoLike MCP configured in `.mcp.json`
- **Always run `account-status` first** to check plan, spend, and quota

## Inputs Required

| Input              | Required     | Example                                 |
| ------------------ | ------------ | --------------------------------------- |
| Seed domain(s)     | One of these | `leadgrow.ai`                           |
| ICP description    | One of these | "B2B outbound lead gen agency for SaaS" |
| Country filter     | Recommended  | `US`, `GB`, `CA`                        |
| Phrase match terms | Optional     | `["cold email", "outbound"]`            |
| Employee range     | Optional     | `"50,500"`                              |
| Category filter    | Optional     | `SAAS`, `HEALTHCARE`                    |

You need **at least one** of: seed domain or ICP description.

---

## Process

> **Cost target: ~$1.50 for a full workflow (5 API calls).**
> Front-load intelligence, minimize API calls. Never run exploratory calls — know what you want before you search.

### Step 0: Check Account & Budget

```
mcp__discolike__account-status
```

Note plan, MTD spend, and remaining budget. Report to user.

### Step 1: Scrape & Analyze the Seed Domain

**This is the most important step.** Extract the company's website text FIRST, then use Claude to build a tight ICP definition before touching discover.

```
mcp__discolike__extract-website-text
  domain: "example.com"
```

From the extracted text, define:

1. **ICP text** — a 1-2 sentence description of what this company does and who they serve
2. **Phrase match terms** — 2-3 exact phrases that would appear on similar companies' sites
3. **Category** — the industry classification
4. **Negation terms** — what to exclude (e.g., if they're B2B, negate "consumer", "B2C")

**Example from leadgrow.ai:**

- ICP text: `"B2B outbound lead generation agency that books meetings using cold email for SaaS companies"`
- Phrases: `["cold email"]` (most specific single term)
- Category: `ADVERTISING_AND_MARKETING`
- Negate: enterprises, recruitment agencies

**Cost:** ~$0.003. This one cheap call saves you 3-4 exploratory discover calls later.

### Step 2: Size the Universe (One Count Call)

Run a single count with your tightest filter to validate the market exists:

```
mcp__discolike__count-matching-domains
  filters: { category: ["..."], country: ["US"], phrase_match: ["cold email"] }
```

If count is <50, loosen filters. If >10,000, tighten. You want 100-5,000 range for discovery.

**Cost:** ~$0.10.

### Step 3: Precision Discovery (One Call)

Combine EVERYTHING into a single discover call. Domain seed + ICP text + phrase match + filters all at once.

```
mcp__discolike__discover-similar-companies
  filters: {
    domain: ["example.com"],
    icp_text: "[from Step 1]",
    phrase_match: ["[from Step 1]"],
    country: ["US"],
    max_records: 10
  }
  fields: ["domain", "name", "similarity", "score", "employees", "description"]
```

> **CRITICAL: phrase_match uses OR logic between items.**
> `["cold email", "outbound"]` returns companies mentioning EITHER term.
> For AND, use a single specific phrase or run 2 queries and intersect.

**Cost:** ~$0.10 per query. Start with 10, scale after validation.

### Step 5: Iterative Refinement

Review results with the user. Then refine:

- **Good fits** → add to `domain` parameter as positive examples (up to 10)
- **Bad fits** → add to `negate_domain` parameter (up to 10)
- **Wrong categories** → add to `negate_category`
- **Wrong concepts** → use `negate_icp_text`

```
mcp__discolike__discover-similar-companies
  filters: {
    domain: ["example.com", "good-fit-1.com", "good-fit-2.com"],
    negate_domain: ["bad-fit.com", "too-big-corp.com"],
    icp_text: "...",
    phrase_match: ["..."],
    country: ["US"],
    max_records: 25
  }
```

**Repeat until top 20-30 results look accurate, then scale up `max_records`.**

### Step 6: Enrich Top Results

For the final list, pull business profiles for top results:

```
mcp__discolike__business-profile
  domain: "[each domain]"
  fields: ["domain", "name", "score", "description", "address", "industry_groups", "social_urls", "public_emails"]
```

Run in parallel for the top 5-10 domains. Present enriched table to user.

**Cost:** ~$0.003/record.

### Step 7: Export to CSV

**Always save results as CSV.** Combine discovery data with enrichment into a single file.

```
output/[seed-domain]-lookalikes-[YYYY-MM-DD].csv
```

**CSV columns:**

```
domain,name,score,similarity,employees,city,state,country,public_emails,social_urls,description
```

- Use semicolons to delimit multiple values within a cell (emails, socials)
- Wrap description in quotes (contains commas)
- Save to `skills/research/discolike-discovery/output/` or client folder if specified

### Step 8: Save to DiscoLike (Optional)

Save the discovered domains as an exclusion list for future queries:

```
mcp__discolike__save-exclusion-list
  query_name: "Client X - B2B Outbound Agencies - 2026-02"
  domains: ["domain1.com", "domain2.com", ...]
```

---

## Cost Reference

**Pricing = per-query fee + per-record fee.** See `references/discolike-field-reference.md` for full plan breakdown.

### Starter Plan Costs (current plan)

| Component                  | Cost  |
| -------------------------- | ----- |
| Per query submission       | $0.18 |
| Per 1,000 records returned | $3.50 |

### Workflow Cost Examples

| Workflow                                   | Calls | Records | Cost       |
| ------------------------------------------ | ----- | ------- | ---------- |
| extract + count + discover(10) + 3x enrich | 5     | ~14     | **~$0.95** |
| Same but discover(100)                     | 5     | ~104    | **~$1.26** |
| Sloppy: 10 exploratory calls, 200 records  | 10    | ~200    | **~$2.50** |

Always report running cost total to the user. **Goal: 5 billable calls max.**

## Output Format

### Discovery Results Table

| Domain      | Company     | Score | Similarity | Employees | Description |
| ----------- | ----------- | ----- | ---------- | --------- | ----------- |
| example.com | Example Inc | 450   | 92         | 51-200    | ...         |

### Enriched Profile

| Field       | Value             |
| ----------- | ----------------- |
| Domain      | example.com       |
| Name        | Example Inc       |
| Score       | 450               |
| Industry    | SAAS (0.85)       |
| Address     | City, State       |
| Social      | LinkedIn, Twitter |
| Description | ...               |

---

## Key Behaviors

1. **Scrape BEFORE you search** — extract-website-text first, define ICP from real content, THEN discover
2. **One discover call, not three** — combine domain + icp_text + phrase_match in a single call
3. **5 API calls max** — extract → count → discover → enrich top 3. That's it.
4. **phrase_match is OR, not AND** — each term matches independently
5. **Start small (5-10 records)** — scale up only after results look right
6. **Track costs** — report running total at each step
7. **Use columnar format** for large result sets (more compact)

## Common Mistakes

| Mistake                                             | Fix                                                  |
| --------------------------------------------------- | ---------------------------------------------------- |
| Jumping straight to discover without scraping first | Run extract-website-text, define ICP, THEN discover  |
| Running 3-4 separate discover calls to "explore"    | Combine all filters into ONE call. Explore = waste.  |
| Fetching 1000 records on first query                | Start with 5-10, scale after validation              |
| Assuming phrase_match is AND                        | It's OR — intersect manually if you need AND         |
| Skipping the count step                             | Always count first to understand universe size       |
| Not checking account-status                         | Always check plan/budget before starting             |
| Requesting fields not available on endpoint         | Check field reference — `employees` is discover-only |
| Using plan-gated features on Starter                | Check feature matrix in references                   |

## Integration Points

| Direction  | Skill                  | Purpose                                    |
| ---------- | ---------------------- | ------------------------------------------ |
| Upstream   | situation-miner        | Provides ICP context and buying situations |
| Upstream   | icp-qualification      | Provides qualification criteria            |
| Upstream   | offer-clarity-workshop | Provides target persona definitions        |
| Downstream | cold-email-v2          | Write outreach for discovered companies    |
| Downstream | waterfall-enrich       | Find contact emails for prospects          |
| Downstream | enrich-company         | Deep-dive individual companies             |
