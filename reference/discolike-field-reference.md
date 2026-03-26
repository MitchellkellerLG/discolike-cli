# DiscoLike Field & Feature Reference

## Available Fields by Endpoint

### discover-similar-companies

| Field | Description |
|-------|-------------|
| domain | Company domain (unique ID) |
| name | Company name from certificate/website |
| status | Operating status + confidence |
| score | Digital footprint score (1-800) |
| start_date | First certificate date |
| end_date | Company end date (if closed) |
| address | HQ address |
| phones | Phone numbers from website |
| public_emails | Contact emails from website |
| domain_associations | Associated domains |
| social_urls | Twitter, LinkedIn, Facebook URLs |
| redirect_domain | Redirect target domain |
| description | Website meta description |
| keywords | NLP-generated keyword:confidence pairs |
| industry_groups | Top 2 industries:confidence pairs |
| update_date | Last record update |
| similarity | Match score 0-100 vs query |
| employees | Employee range bucket |
| vendors | Tech vendors (when tech_stack filter used) |

### business-profile

Same as discover EXCEPT: **no `employees`, `similarity`, or `vendors` fields.**

### digital-footprint-score

| Field | Description |
|-------|-------------|
| domain | Normalized domain |
| score | Final score (0-999) |
| parameters | Breakdown: base_score, recency_multiplier, growth_boost, lookback_360/720, expiration_penalty |
| first_event | Date of first certificate |

### growth-metrics

| Field | Description |
|-------|-------------|
| domain | Normalized domain |
| score_growth_3m | Score growth rate, last 3 months |
| subdomain_growth_3m | Subdomain growth rate, last 3 months |
| score_YYYYQX | Quarterly score (5 quarters) |
| subdomains_YYYYQX | Quarterly subdomain count (5 quarters) |

### count-matching-domains

Returns: `{ count: number }` — no field selection needed.

### extract-website-text

Returns: `{ domain, text }` — cached/pre-crawled content only.

### save-exclusion-list

Returns: `{ query_id, query_name, domain_count }`.

### list-saved-queries

| Field | Description |
|-------|-------------|
| query_id | Unique ID |
| query_name | User-provided name |
| action | Endpoint type |
| user_name | Creator |
| mtime | Creation timestamp |
| domains | Array of domains |
| domain_count | Number of domains |
| query_params | Original query parameters |

### usage-statistics

| Field | Description |
|-------|-------------|
| account_status | Active/inactive |
| month_to_date_requests | MTD request count |
| month_to_date_records | MTD record count |
| month_to_date_spend | MTD spend ($) |
| max_spend | Monthly spend cap |
| total_available_spend | Available budget |
| carryover_credits | Carryover from prior months |
| top_up_credits | Additional credits |
| usage_summary | Monthly breakdown by user |

---

## Pricing

Full subscription price goes toward query credits. Two cost components per call:

### Per-Query + Per-Record Costs

| | Starter | Pro | Team | Company | Enterprise |
|---|---|---|---|---|---|
| **Monthly price** | $99 | $199 | $399 | $799 | $1,599 |
| **Per query** | $0.18 | $0.15 | $0.12 | $0.10 | $0.08 |
| **Per 1,000 records** | $3.50 | $3.00 | $2.50 | $2.00 | $1.50 |
| **Max exclusion records** | 0 | 25,000 | 50,000 | 100,000 | 200,000 |

### Cost Formula

```
total_cost = query_fee + (records_returned / 1000) × record_fee
```

### Example Costs (Starter Plan)

| Call | Query Fee | Records | Record Fee | Total |
|------|-----------|---------|------------|-------|
| count-matching-domains | $0.18 | 0 | $0.00 | **$0.18** |
| extract-website-text | $0.18 | 1 | $0.004 | **$0.18** |
| discover (10 records) | $0.18 | 10 | $0.04 | **$0.22** |
| discover (100 records) | $0.18 | 100 | $0.35 | **$0.53** |
| discover (1000 records) | $0.18 | 1000 | $3.50 | **$3.68** |
| business-profile (1 domain) | $0.18 | 1 | $0.004 | **$0.18** |
| **Optimized workflow (5 calls)** | $0.90 | ~14 | $0.05 | **~$0.95** |

### All Plans Include

- Full firmographic profiles (60M companies)
- Up to 10,000 result records per query
- Lookalike domain consensus search
- ICP text wizard / natural language search
- Homepage exact phrase matching
- Social media and mobile app targeting
- Targeting by company start date

---

## Plan Feature Matrix

| Feature | Starter | Pro | Team | Company | Enterprise |
|---------|---------|-----|------|---------|------------|
| Discover similar companies | YES | YES | YES | YES | YES |
| Count matching domains | YES | YES | YES | YES | YES |
| Business profile | YES | YES | YES | YES | YES |
| Digital footprint score | YES | YES | YES | YES | YES |
| Growth metrics | YES | YES | YES | YES | YES |
| Extract website text | YES | YES | YES | YES | YES |
| Saved queries | YES | YES | YES | YES | YES |
| Usage statistics | YES | YES | YES | YES | YES |
| Market segmentation | - | YES | YES | YES | YES |
| Company matching | - | - | YES | YES | YES |
| Vendor/tech data | - | - | YES | YES | YES |
| Public company links | - | - | - | - | YES |
| Subsidiaries/parent | - | - | - | - | YES |
| Domain redirects | - | - | - | - | YES |

---

## Discovery Filter Reference

### Positive Filters (narrow results)

| Filter | Type | Example |
|--------|------|---------|
| domain | array (up to 10) | `["hubspot.com", "salesforce.com"]` |
| icp_text | string | `"B2B marketing automation SaaS"` |
| country | array (ISO alpha-2) | `["US", "GB"]` |
| state | array | `["CA", "NY"]` (single country only) |
| employee_range | string | `"50,500"` |
| category | array | `["SAAS", "HEALTHCARE"]` |
| language | array (ISO-639-2) | `["en", "de"]` |
| phrase_match | array (up to 20) | `["cold email", "outbound"]` |
| social | array | `["linkedin", "twitter"]` |
| min_digital_footprint | int (0-800) | `100` |
| max_digital_footprint | int (0-800) | `600` |
| min_similarity | int (0-99) | `70` |
| start_date | string | `"2020-01-01"` |

### Negation Filters (exclude results)

| Filter | Type | Example |
|--------|------|---------|
| negate_domain | array (up to 10) | `["too-big.com"]` |
| negate_icp_text | string | `"enterprise consulting"` |
| negate_country | array | `["CN", "RU"]` |
| negate_category | array | `["FINANCIAL_SERVICES"]` |
| negate_phrase_match | array (up to 20) | `["recruitment"]` |
| negate_language | array | `["zh"]` |
| negate_social | array | `["tiktok"]` |

### Special Flags

| Flag | Default | Purpose |
|------|---------|---------|
| auto_icp_text | false | Auto-generate ICP text from seed domain(s) |
| auto_phrase_match | false | Auto-generate phrases from ICP text |
| enhanced | false | AI-powered result enhancement |
| include_search_domains | false | Include seed domains in results |
| redirect | false | Include redirecting domains |
| variance | UNRESTRICTED | Result diversity: LOW → UNRESTRICTED |
| consensus | 1 | Top N results for search vector (1-20) |

---

## Industry Categories

ACCOUNTING, ADVERTISING_AND_MARKETING, AGRICULTURE_AND_NATURAL_RESOURCES, AUTOMOTIVE, BIG_DATA_AND_ANALYTICS, BIOTECHNOLOGY, BLOCKCHAIN_AND_CRYPTOCURRENCY, BUSINESS_PRODUCTS_AND_SERVICES, CLOUD_COMPUTING, COMPUTER_HARDWARE_AND_SEMICONDUCTORS, CONSTRUCTION, CONSUMER_PRODUCTS, CONSUMER_SERVICES, CYBERSECURITY, DEFENSE_AND_AEROSPACE, E-COMMERCE, EDUCATION, ENERGY, ENGINEERING, ENTERTAINMENT, ENVIRONMENTAL_SERVICES, FASHION_TEXTILE_AND_APPAREL, FINANCIAL_SERVICES, FOOD_AND_BEVERAGE, GAMING_AND_ESPORTS, GOVERNMENT_SERVICES, HEALTHCARE, HOSPITALITY, HUMAN_RESOURCES, INSURANCE, IT_SERVICES, LEGAL, MANUFACTURING, MEDIA, MINING_AND_METALS, NONPROFIT_AND_PHILANTHROPY, OIL_AND_GAS, PHARMACEUTICALS, PRIVATE_EQUITY_AND_VENTURE_CAPITAL, REAL_ESTATE, RENEWABLE_ENERGY, RESTAURANTS, RETAIL, SAAS, SECURITY, SOFTWARE, SPORTS_AND_RECREATION, SUPPLY_CHAIN_AND_PROCUREMENT, TELECOMMUNICATIONS, TRAVEL, WELLNESS_AND_LIFESTYLE

---

## Employee Range Buckets

`1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+`

Format for filter: `"min,max"` e.g. `"50,500"` maps to buckets `51-200` and `201-500`.