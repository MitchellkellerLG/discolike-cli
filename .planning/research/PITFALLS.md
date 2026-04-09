# Domain Pitfalls

**Domain:** CLI tool — async task management, iterative AI feedback loops, credit-consuming APIs
**Researched:** 2026-04-08
**Confidence:** HIGH (based on API reference docs, existing client.py/cost.py code, DiscoLike plan constraints)

---

## Critical Pitfalls

Mistakes that cause rewrites, runaway spend, or broken user trust.

---

### Pitfall 1: Feedback Loop Quota Burn Without User Awareness

**What goes wrong:** The OLM feedback loop runs `discover` on every iteration. Each call costs $0.18 query fee + per-record fees. A user doing 5 refinement rounds on 25 records spends ~$1.15 before reaching the TAM query — and they never saw a cost warning. An agent auto-iterating burns this silently.

**Why it happens:** `CostTracker.record_call()` accumulates correctly but only warns at 80%/95% of the _session budget_, not per-iteration spend. When the loop is interactive, the user never explicitly approved "5 more discover calls to converge." The current client has no concept of "loop iteration cost" vs "one-off call cost."

**Consequences:** Unexpected bill, user distrust of the tool, agents that auto-iterate to convergence burning $5+ on a single discovery session.

**Prevention:**
- Before each feedback loop iteration (after the first), display cumulative loop cost: "Iteration 2 of 5 — loop cost so far: $0.36. Continue? [Y/n]"
- Add a `--max-iterations N` flag (default: 3) that hard-caps loop rounds without explicit override
- Display per-iteration cost breakdown alongside the query plan diff, not just in the footer
- For agent mode (`--json`), include `loop_cost_so_far` and `iterations_remaining` in the `_meta` block so the calling agent can decide whether to continue

**Warning signs:**
- Loop runs >3 iterations without a cost checkpoint
- `--json` mode with no budget field in `_meta`
- Absence of a `max_iterations` guard in the loop implementation

**Phase:** LOOP-01, LOOP-02 (feedback loop core) — must be addressed before any loop goes to testing

---

### Pitfall 2: DiscoGen Cost Surprise — Credits + Model Fees Stack

**What goes wrong:** DiscoGen charges _two separate fees per record_: DiscoLike credits (for fetching context via `website`/`profile` mode) plus LLM model fees (for running the prompt). On `website` context mode with web search enabled, each domain costs credits + model tokens + search API calls. Processing 500 domains looks like one task but has three independent cost meters running.

**Why it happens:** The `CostTracker` currently models costs as `per_query + per_1k_records` based on DiscoLike API billing. DiscoGen's LLM fees are billed separately through the BYOM provider (OpenAI in this case) — they never appear in `X-DiscoLike-Cost` headers. The existing cost model has no slot for external LLM fees.

**Consequences:** User sees `$0.50` in the DiscoLike cost footer but gets a $3.00 OpenAI charge the next day. No way to estimate before submitting a large batch. Runaway spend on `web_search: true` jobs where search queries multiply per record.

**Prevention:**
- Before submitting a DiscoGen job, display a pre-flight cost estimate: "~N domains × context_mode=website + prompt = est. $X in DiscoLike credits (LLM fees billed separately by your provider)"
- For `web_search: true`, add an explicit warning: "Web search multiplies cost — each domain triggers additional search API calls"
- Surface `estimated_cost` from the DiscoGen status response in the progress display, not just at completion
- Add a `--cost-limit` flag for DiscoGen that cancels the task if `estimated_cost` from status polling exceeds the threshold
- Never combine `web_search: true` with large batches (>100 domains) without explicit confirmation

**Warning signs:**
- DiscoGen job submitted with `web_search: true` and >50 domains without a pre-flight estimate
- Cost footer shows only DiscoLike credits, no note about LLM fees
- `context_mode=website` used as default without surfacing credit consumption

**Phase:** GEN-01, GEN-02, GEN-03

---

### Pitfall 3: Async Poll Stalls — Task ID Lost Between CLI Invocations

**What goes wrong:** DiscoGen, Validate ICP, and Segment are all async (submit → `task_id` → poll). If the CLI exits or the user Ctrl+C's during submission, the `task_id` is lost. The job continues running on the server (burning credits), but the user has no way to check status or retrieve results without re-running the full job.

**Why it happens:** There's no persistence layer for in-flight task IDs. The existing SQLite cache (`~/.discolike/cache.db`) only stores API responses, not task metadata. A task submitted in one terminal session is invisible to a subsequent `discolike discogen status` call.

**Consequences:** Duplicate job submissions (user thinks it failed, resubmits — now two jobs run, double the cost). Results permanently lost if the terminal closed before polling completed. No way to audit what jobs were run.

**Prevention:**
- On every async task submission, immediately persist `{task_id, endpoint, submitted_at, params_hash, status}` to SQLite before any polling begins
- Add `discolike tasks list` and `discolike tasks status <task_id>` subcommands that read from this persisted store
- On graceful exit (Ctrl+C during polling), print: "Task still running: `discolike discogen status <task_id>`"
- Signal handler (`SIGINT`) must print the task_id to stderr before exiting — never silently abandon a running task

**Warning signs:**
- No SQLite table for in-flight tasks in the schema
- `task_id` only stored in a local variable inside the polling loop
- No output of `task_id` to stderr before polling begins

**Phase:** GEN-03 (async task management) — the shared task manager must address this before any async command ships

---

## Moderate Pitfalls

---

### Pitfall 4: Aggressive Polling Burns Rate Limits on Segment (2 req/min)

**What goes wrong:** Segment has the tightest rate limit in the API: 2 req/min base on Starter (the current plan). If the polling loop for segment status uses a short interval (e.g., 5s), it will exhaust this limit and start getting 429s. The existing `_request()` retry logic handles 429 with backoff — but exponential backoff inside a polling loop creates compound delays that make the tool feel broken.

**Why it happens:** The current client's `_request()` backoff is designed for transient errors on one-off calls. Polling is a fundamentally different pattern — it's expected to take minutes, not retry in seconds. Using the same backoff logic for polling conflates error recovery with progress checking.

**Prevention:**
- Polling interval for segment: minimum 30s (2 req/min limit means >30s between polls to stay safe)
- Polling interval for DiscoGen/Validate: minimum 10s (no documented rate limit on `/discogen/status`, but courtesy minimum)
- Implement adaptive polling: short initial check (10-15s after submission), then increasing intervals (30s, 60s) as the task ages
- Never use the retry logic in `_request()` for status polling — use a separate poll loop with explicit sleep intervals

**Warning signs:**
- Status polling using intervals shorter than 30s for segment
- Shared retry/backoff logic used for both error recovery and polling
- No distinction between "task still running" (poll again) and "request failed" (retry)

**Phase:** VAL-02, GEN-03, SEG-03 (all async polling commands)

---

### Pitfall 5: X-Applied-Filters Parsing Failure Breaks the OLM Loop

**What goes wrong:** The entire OLM feedback loop depends on reading `X-Applied-Filters` from the discover response header to understand what the API actually applied vs what was submitted. This header contains a JSON object. If parsing fails (malformed JSON, unexpected schema, header absent on error responses), the loop has no ground truth to show the user and must either abort or silently skip the diff display.

**Why it happens:** The current `discover()` method in `client.py` (line 292-302) returns `DiscoverResult` from the JSON body — it never touches response headers. Headers are discarded after the `_request()` call returns. There's no defensive handling for absent or malformed headers.

**Prevention:**
- The `discover()` method must be extended to return (or expose) the raw `X-Applied-Filters` header value alongside the result
- Parse defensively: `json.loads()` wrapped in try/except, fall back to empty dict if absent or malformed
- In the feedback loop, treat a missing `X-Applied-Filters` as "API applied unknown filters" — display as a warning, don't block the loop
- Add a test fixture with the header present, absent, and malformed to validate all three paths

**Warning signs:**
- `discover()` discards the response headers object after getting the body
- No test coverage for `X-Applied-Filters` absent scenario
- Feedback loop display assumes the header is always present and valid

**Phase:** LOOP-01 (query plan display) — critical path for the first phase

---

### Pitfall 6: Iterative Refinement Loses Convergence Context

**What goes wrong:** The OLM loop accumulates positive/negative domain examples across iterations. By iteration 3, the user has added 4 good-fit domains and 3 bad-fit domains to the query. If this state isn't persisted in the loop's data structure (only the current iteration's discover result is kept), each refinement resets to "blank slate" and the user has to re-specify corrections they already made.

**Why it happens:** It's easy to structure the loop as "show results → ask for corrections → resubmit" without carrying forward the accumulated filter delta from all previous iterations. Each resubmission only includes the filters from the most recent correction, not the union of all prior corrections.

**Prevention:**
- Maintain a mutable `QueryState` dataclass across loop iterations: `{domain_seeds: [], negate_domains: [], phrase_match: [], negate_phrase_match: [], ...}`
- Each iteration _merges_ user corrections into `QueryState`, never replaces it
- Display a compact "accumulated refinements" summary at the start of each iteration (e.g., "+3 good domains, -2 bad domains, +1 phrase")
- In `--json` mode, include the full accumulated `query_state` in `_meta` so agents can track convergence

**Warning signs:**
- Loop variables for positive/negative examples are reset each iteration
- No summary of accumulated changes shown between iterations
- `_meta` in JSON mode only contains the current iteration's params

**Phase:** LOOP-01, LOOP-02

---

### Pitfall 7: Validate ICP Uses DiscoGen Status Endpoint (Cross-Endpoint Dependency)

**What goes wrong:** According to the API docs, `/validate/icp` uses `/discogen/status/{task_id}` for polling — not a dedicated `/validate/status/` endpoint. This means the Validate command shares polling infrastructure with DiscoGen. If someone implements them as two separate polling implementations, they'll diverge. More critically, if the shared polling logic doesn't know the _type_ of task it's polling, it can't parse the result correctly (DiscoGen returns `results` keyed by domain; Validate ICP returns `results` as an object with domain → Fit/Confidence/Reasoning schema).

**Why it happens:** The API decision to share status endpoints is not obvious from endpoint names. Easy to implement `/validate/icp` polling as if it had its own status endpoint.

**Prevention:**
- The shared `AsyncTaskManager` must accept a `result_parser` callback or task type enum so result parsing is task-specific while polling logic is shared
- Document explicitly in code: "Validate ICP polls via `/discogen/status/{task_id}` — not a dedicated endpoint"
- Test: submit a validate job, poll via the shared manager, confirm the result schema matches the Validate response shape

**Warning signs:**
- Validate and DiscoGen have two separate polling implementations
- No test that verifies Validate polling uses the discogen status endpoint

**Phase:** VAL-02, GEN-03 — must be designed together, not in isolation

---

## Minor Pitfalls

---

### Pitfall 8: `--confirm` Flag UX — User Confusion About When Loop Ends

**What goes wrong:** Without a clear "this is your last iteration, do you want to run full TAM?" prompt, users don't know when to escalate from probe queries (small `max_records`) to the full TAM query (large `max_records`). They keep refining with 10-record samples when they could have already scaled.

**Prevention:**
- After each iteration, show: current result quality signals (similarity distribution, top domains) plus a suggested next action: "Results look stable — ready to scale to full TAM? (run with max_records=500)"
- Distinguish the loop's "convergence check" from the "scale-up confirm" — two separate decision points

**Phase:** LOOP-02, LOOP-03

---

### Pitfall 9: Segment is Pro+ Only — Not Clearly Surfaced at Command Entry

**What goes wrong:** `segment` is behind a Pro+ plan gate. Starter users who try to run it get a 403 from the API after filling in all flags. The error message from the API is generic ("Forbidden"), not actionable.

**Prevention:**
- On `discolike segment` invocation, check `account_status()` first (cached 1h) and fail fast with a clear message: "Segment requires Pro+ plan. Current plan: Starter."
- Gate the plan check at command entry, before any flag validation

**Phase:** SEG-01

---

### Pitfall 10: Dry Run Doesn't Cover Async Task Submission

**What goes wrong:** The existing `dry_run` flag prevents actual API calls for synchronous endpoints. For async tasks (DiscoGen, Validate, Segment), a dry run that short-circuits at `task_id` return is fine — but if the task submission itself is allowed to proceed (to "test" the submission), the job starts running and charges begin.

**Prevention:**
- `dry_run=True` must intercept async task submission, not just polling
- Return a fake `task_id` in dry run mode, then simulate a polling sequence with fake progress/completion responses
- Add tests for dry run of async commands to ensure no actual HTTP requests are made

**Phase:** GEN-01, VAL-01, SEG-01

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| LOOP-01 (query plan) | X-Applied-Filters absent or malformed | Defensive parse, graceful fallback |
| LOOP-02 (convergence) | Accumulated refinements lost between iterations | Mutable `QueryState`, carry-forward pattern |
| LOOP-01/02 (cost) | Quota burned silently across iterations | Per-iteration cost gate, `--max-iterations` default |
| GEN-01/02 (DiscoGen) | Credits + LLM fees both invisible | Pre-flight estimate, dual-cost display |
| GEN-03 (task manager) | task_id lost on exit | SQLite persistence before first poll |
| VAL-02 (validate polling) | Separate polling impl diverges from DiscoGen | Shared `AsyncTaskManager` with result_parser |
| GEN-03 / SEG-03 (polling) | Aggressive polling hits 2 req/min segment limit | 30s minimum interval for segment, adaptive intervals |
| SEG-01 (segment) | 403 after flag entry for Starter users | Plan gate at command entry, not at API call |
| All async commands | Dry run allows task submission | Intercept at submission, not at poll |

## Sources

- DiscoLike API Reference (`leadgrow-hq/archive/mcp-docs/DiscoLike_API_Reference.md`) — rate limits, async task flows, pricing model, X-Applied-Filters header, plan gating
- `src/discolike/client.py` — existing retry/backoff pattern, response header handling gap, discover() response parsing
- `src/discolike/cost.py` — budget tracking model, warning thresholds, CostBreakdown schema
- `reference/discolike-workflow.md` — iterative refinement patterns, per-iteration cost targets
- PROJECT.md — confirmed Starter plan, BYOM configured (OpenAI), rate limit constraints
