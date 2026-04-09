# Feature Landscape: DiscoLike CLI v2 — OLM Feedback Loop & AI Discovery

**Domain:** B2B discovery/enrichment CLI with iterative query refinement
**Researched:** 2026-04-08
**Sources:** PROJECT.md (validated requirements), DiscoLike_API_Reference.md (API contracts), discolike-discovery/SKILL.md (existing v1 workflow)

---

## What This Milestone Is Actually Building

The v1 CLI is one-shot: fire a discover call, get results, done. v2 adds a closed feedback loop between two models — Claude Code (which knows the client context) and DiscoLike's search model (which knows what filters it actually applied). The loop runs until the query plan converges, then executes the full TAM pull with confidence.

Three capability clusters being added:
1. **OLM feedback loop** — expose `X-Applied-Filters`, present query plan, iterate until confirmed
2. **AI enrichment pipeline** — DiscoGen (domain/contact prompts) + Validate ICP (LLM-scored fit)
3. **Auto-segmentation** — cluster a domain list into meaningful groups

Plus a new interactive multi-dimensional discovery skill that replaces the current 8-step MCP workflow.

---

## Table Stakes

Features where absence makes the feedback loop useless or the async operations unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Query plan extraction from `X-Applied-Filters`** | Without this the loop has no feedback signal — you can't know what DiscoLike actually applied vs what you submitted | Low | Response header, parse to JSON. Maps to LOOP-01. |
| **Structured query plan display** | User/agent must see what's active: lookalike text, phrase matches, industry groups, filters, what was ignored. Without this there's nothing to react to | Low-Med | Rich table or JSON depending on TTY. Maps to LOOP-01. |
| **`--confirm` flag on `discover`** | Existing one-shot behavior must not break. Scripts and automation can't suddenly go interactive. Feedback loop is opt-in. | Low | Boolean flag, no default change. Maps to LOOP-03. |
| **Resubmission with explicit params** | The refinement mechanism — take what DiscoLike extracted, allow user to override, resubmit with explicit params instead of relying on auto-extraction | Med | Build from existing discover params. Maps to LOOP-01, LOOP-02. |
| **Convergence confirmation gate** | Loop must halt on explicit confirm, not just "looks good enough." Without a clear gate, the loop runs indefinitely or stops arbitrarily | Low | `--confirm` prompt in interactive mode, `--json` flag for agent confirm. Maps to LOOP-02. |
| **Machine-readable query plan output** | Claude Code agents can't parse Rich tables. Must output structured JSON for agent-in-the-loop workflows | Low | `--json` on query plan display. Maps to LOOP-04. |
| **Async task manager (shared)** | DiscoGen, Validate ICP, and Segment all use `task_id` → poll → results. Without consistent polling/progress/cancel logic, each command has its own buggy implementation | Med | Single shared class/module. Maps to GEN-03, VAL-02, SEG-03. |
| **Poll with progress display** | Async ops can take minutes (10k domains). Without progress feedback the CLI looks hung | Low-Med | Rich progress bar on TTY, silent on JSON. Required for all three async commands. |
| **`discolike validate` command** | ICP validation is the primary quality gate after discovery — score domains against ICP before burning quota on enrichment | Low | Wraps `/validate/icp`. Maps to VAL-01. |
| **Validate → discover pipe** | Discovery outputs a domain list. Validation scores that list. Without direct piping, user manually copies domains between commands | Med | Accept stdin or `--input` file of domains. Maps to VAL-03. |
| **`discolike discogen` command** | Core AI enrichment — run LLM prompts against domains. Without this there's no AI enrichment capability at all | Med | Wraps `/discogen/process`. Maps to GEN-01. |
| **Cumulative cost display during iterations** | Feedback loop consumes quota on each iteration. Rate limits are 5 req/min on Starter. User must see running cost before each resubmission or they'll blow their budget unknowingly | Low | Extend existing cost tracking to loop iterations. Maps to constraint in PROJECT.md. |
| **Pre-iteration count call** | Before re-running discover with refined params, run count first to show universe size change. Prevents wasted discover calls on degenerate queries (count < 50 = tighten, > 10k = loosen) | Low-Med | Existing `count` endpoint. Fits between plan display and resubmission. |

---

## Differentiators

Features that distinguish this from a thin API wrapper or a basic polling loop.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Multi-dimensional seed analysis phase** | Before the user touches discover params, decompose seed domains across 5 axes: what they sell, who they sell to, industry, size, geo. Claude Code does this from BizData + Extract. This is the intelligence layer that makes the query plan actually good | Med | Uses BizData + Extract endpoints. Maps to SKILL-02. |
| **Dimension weighting guidance** | After seed analysis, guide the user through tightening vs loosening each dimension independently. "Your size filter is cutting 80% of the market — loosen to 11-500?" This is the judgment layer above raw filter adjustment | High | Interactive prompt logic in skill. Maps to SKILL-03. |
| **Query plan diff view between iterations** | Show what changed between iteration N and N+1 — not just the current plan, but what was added, removed, or modified. Without this the user can't tell if their adjustments had any effect | Med | Diff the two `X-Applied-Filters` JSON objects. |
| **Variance and consensus dimension controls** | Expose `variance` (LOW/MID_LOW/MEDIUM/MID_HIGH/HIGH/UNRESTRICTED) and `consensus` (1-20 search vectors) in the feedback loop UI. These are the precision vs recall knobs most users never touch because they're invisible | Low | Already supported by discover endpoint. Needs UX surfacing. |
| **Post-discovery pipeline orchestration** | After discovery converges, surface an optional next-step prompt: validate → enrich → segment. This is the v1 skill's "after discovery" section made explicit and automated | High | Maps to SKILL-05. Connects all three new capability clusters. |
| **Interim results display during DiscoGen** | DiscoGen returns `interim_results` in status polls. Show these as they arrive rather than waiting for 100% completion. For large batches (10k domains) this means actionable data in minutes, not hours | Med | Maps to GEN-03. Requires careful Rich output management (don't corrupt JSON stream). |
| **Context mode selection for DiscoGen/Validate** | `website` (most context, most cost) vs `profile` (fast) vs `domain` (cheapest). Surface this as an explicit prompt with cost implications explained. Most users will default to `website` and overpay | Low | Maps to GEN-04. Cost transparency = fewer surprises. |
| **BYOM config management** | `discolike llm-providers` CRUD — list, create, test, set-default. BYOM is already configured (OpenAI + Serper keys in account), but there's no CLI surface to manage or inspect it | Med | Maps to GEN-05, GEN-06. Wraps `/llm-providers/*` and `/search-providers/*` endpoints. |
| **`discolike discogen personas`** | Run LLM prompts against contacts (persona_ids), not just domains. Opens AI enrichment to the contact layer — qualify specific people, not just companies | Med | Maps to GEN-02. Wraps `/discogen/process-personas`. |
| **`discolike segment` with progress** | Auto-cluster a domain list into segments with natural-language labels. Transforms a flat CSV into a segmented list with business-similarity groupings | Med | Maps to SEG-01, SEG-02, SEG-03. Pro+ gated. |
| **Validate Fit/Confidence/Reasoning display** | The three-column ICP validation output (Fit: yes/partial/no, Confidence: high/medium/low, Reasoning: 1-2 sentence) is highly actionable. Surface it in a sorted table — yes+high at top, no+high excluded | Low | Formatting over the existing validate response structure. |
| **Upgraded multi-dimensional discovery skill** | Replace the current 8-step MCP-based SKILL.md with a CLI-native skill that exercises the feedback loop, seed analysis, and post-discovery pipeline. This is the skill users and agents will actually run | High | Maps to SKILL-01 through SKILL-05. |

---

## Anti-Features

Things to deliberately not build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Auto-accept convergence without user/agent gate** | The loop exists to surface judgment. Auto-accepting when DiscoLike stops changing filters removes the human-in-the-loop value entirely | Always require explicit confirm (`--confirm` or agent JSON response) |
| **Polling with fixed sleeps** | Fixed sleeps (e.g., `time.sleep(5)`) between polls waste time on fast jobs and burn CPU on slow ones | Use exponential backoff with a cap. Start at 2s, cap at 30s. |
| **Separate polling logic per command** | DiscoGen, Validate, and Segment all have identical task_id → poll → results patterns. Duplicating this three times guarantees three slightly different bugs | Build one shared async task manager and use it everywhere |
| **Streaming live discover results** | Discover is synchronous and returns a full result set. There's nothing to stream. Simulating streaming with artificial delays adds complexity and misleads the user | Show results when they arrive |
| **History, metrics, redirects, publiclink in this milestone** | These are explicitly out of scope per PROJECT.md — niche endpoints with low discovery workflow value | Defer to future milestones if demand emerges |
| **Storing DiscoGen results in the CLI cache** | DiscoGen job outputs can be large (10k domains) and are time-sensitive. The SQLite cache is designed for repeat lookups (profile, extract), not AI enrichment outputs | Return results directly to stdout/file. Let user manage persistence. |
| **Interactive mode as default for `discover`** | Existing scripts and the list-building pipeline call `discover` in non-interactive mode. Changing the default would break all existing automation silently | `--confirm` flag is opt-in. Default is unchanged one-shot behavior. |
| **Automatic negative examples from bad fits** | During iteration, it's tempting to auto-add bad-fit domains to `negate_domain`. But "bad fit" is a judgment call — the user may have flagged them for reasons the tool can't infer | Present bad-fit domains as suggestions, require explicit confirmation before adding to negate params |
| **Web search enabled by default in DiscoGen/Validate** | `web_search: true` adds cost per record. For large batches this compounds quickly. Default off, user opts in | Default `--web-search` to false. Show cost differential when toggling. |
| **Contact Bulk Match in this milestone** | Explicitly out of scope per PROJECT.md. Batch match is useful but disconnected from the core feedback loop work | Add in a later milestone if demand emerges |

---

## Feature Dependencies

```
SKILL-01 (multi-dimensional discovery skill)
  requires SKILL-02 (seed analysis phase)
  requires SKILL-03 (dimension weighting)
  requires SKILL-04 (query construction + OLM loop)
  requires LOOP-01 + LOOP-02 + LOOP-03 + LOOP-04
  optional SKILL-05 (post-discovery pipeline)
    requires VAL-01 + VAL-02 + VAL-03 (validate)
    requires GEN-01 + GEN-02 + GEN-03 (discogen)
    requires SEG-01 + SEG-02 + SEG-03 (segment, Pro+)

LOOP-01 (X-Applied-Filters extraction + query plan display)
  required by LOOP-02 (convergence flow)
  required by LOOP-03 (--confirm flag)
  required by LOOP-04 (--json machine-readable output)

Shared async task manager
  required by GEN-03 (discogen polling)
  required by VAL-02 (validate polling)
  required by SEG-03 (segment polling)

GEN-01 (discogen domains)
  required by GEN-02 (discogen personas — same command group)
  required by GEN-03 (async management — must exist first)
  optional GEN-04 (context mode selection)
  optional GEN-05 (BYOM config)
  optional GEN-06 (BYOS config)

VAL-01 (validate command)
  required by VAL-02 (async polling — validate is always async)
  required by VAL-03 (pipe from discover output)
```

**Build order implied by dependencies:**
1. Shared async task manager (unblocks all three async command groups)
2. LOOP-01 + LOOP-03 + LOOP-04 (feedback loop core — unblocks skill work)
3. LOOP-02 (convergence gate — completes the loop)
4. VAL-01 + VAL-02 + VAL-03 (validate — simpler async, good to build before discogen)
5. GEN-01 + GEN-03 (discogen core + polling)
6. GEN-02 + GEN-04 + GEN-05 + GEN-06 (discogen extensions)
7. SEG-01 + SEG-02 + SEG-03 (segment — Pro+ gated, test last)
8. SKILL-01 through SKILL-05 (skill upgrade — wraps everything above)

---

## MVP Recommendation

If scope needs to shrink, cut in this order:

**Must ship (loop is useless without these):**
- LOOP-01 through LOOP-04 (the entire feedback loop)
- VAL-01 + VAL-02 + VAL-03 (ICP validation gate)
- Shared async task manager
- Cumulative cost display during iterations

**Should ship (core value of v2):**
- GEN-01 + GEN-03 + GEN-04 (discogen domains with context mode)
- SKILL-01 through SKILL-04 (upgraded skill without post-discovery pipeline)

**Can defer:**
- GEN-02 (discogen personas — contacts layer, separate use case)
- GEN-05 + GEN-06 (BYOM/BYOS config management — already configured in account)
- SEG-01 through SEG-03 (segmentation — Pro+ required, test on correct plan)
- SKILL-05 (post-discovery pipeline orchestration — high complexity, more coordination)

---

## API Constraints That Shape Features

These are hard constraints from the API, not design choices:

| Constraint | Impact |
|------------|--------|
| Discover: 5 req/min on Starter | Feedback loop iterations consume quota. Must show running cost and provide pause/confirm before each resubmit. |
| Segment: 2 req/min base rate | Don't retry-on-failure for segment — one failed call wastes 30 seconds of quota window. |
| Discover: max 10 seed domains, max 10 negate domains | Feedback loop must enforce these limits visibly, not silently truncate. |
| DiscoGen: max 10,000 domains per job | Batch large lists automatically, show per-batch progress. |
| Validate ICP: uses same status endpoint as DiscoGen (`/discogen/status/{task_id}`) | Shared task manager can use one polling path for both. |
| Segment: Pro+ only | Gate cleanly with a helpful error message on Starter plan, not a silent 403. |
| Tech stack filters: Team+ only | Same gating pattern — surface plan requirement in error, not confusing 403. |
| `X-Applied-Filters` is a response header, not body | Parser must explicitly extract headers, not just parse response body. |
| `previous_discogen_data` param enables iterative enrichment | DiscoGen supports chaining runs — pass prior results to add columns without re-processing from scratch. Surface this in the skill post-discovery pipeline. |
