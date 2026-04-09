# DiscoLike CLI v2 — OLM Feedback Loop & AI Discovery

## What This Is

Upgrade the DiscoLike CLI from a one-shot discovery tool into a full discovery-to-action pipeline. Adds the OLM feedback loop (query plan confirmation and iterative refinement), ICP validation, AI-powered enrichment via DiscoGen, and auto-segmentation. Paired with an interactive multi-dimensional discovery skill that guides users through building precise lookalike queries across product, buyer, industry, size, and geo dimensions.

## Core Value

The feedback loop between Claude Code's client context and DiscoLike's search model — both models iterate on the query plan until convergence, then run full TAM queries with confidence.

## Requirements

### Validated

- ✓ Core discovery (`discover`, `count`) with full filter support — v1
- ✓ Company enrichment (`profile`, `score`, `growth`, `extract`) — v1
- ✓ Contact lookup (`contacts`) — v1
- ✓ Name-to-domain resolution (`match`) — v1
- ✓ Bulk firmographic append (`append`) — v1
- ✓ Tech stack detection (`vendors`) — v1
- ✓ Corporate hierarchy (`subsidiaries`) — v1
- ✓ Saved queries and exclusion lists (`saved`) — v1
- ✓ Composite workflows (`workflow discover`, `workflow harvest`) — v1
- ✓ Cost tracking with per-call and session totals — v1
- ✓ Dual output (Rich tables / JSON / CSV) with TTY detection — v1
- ✓ SQLite cache with TTL per endpoint — v1
- ✓ Config management (`config show/set/clear`) — v1
- ✓ Account status and usage (`account status/usage`) — v1
- ✓ Agent-native design (SKILL.md, structured exit codes, `_meta` blocks) — v1
- ✓ Shared async task infrastructure (AsyncTaskManager, SQLite persistence, client submit/status/cancel, Ctrl+C safety, backoff polling) — Phase 1
- ✓ ICP validation command (`discolike validate`) with sorted results, triple input, pipe integration, context modes — Phase 2
- ✓ DiscoGen enrichment commands (`discolike discogen run` + `discogen personas`) with interim display, cost estimates, web-search warnings — Phase 2

### Active

- [ ] **LOOP-01**: OLM feedback loop — capture `X-Applied-Filters` from discover response, present query plan (lookalike text, phrase matches, industry groups, filters), allow review and adjustment, resubmit with explicit params
- [ ] **LOOP-02**: Convergence flow — iterate query plan until user/agent confirms, then execute full TAM query
- [ ] **LOOP-03**: `--confirm` flag on `discover` to enable feedback loop mode (vs one-shot default)
- [ ] **LOOP-04**: Machine-readable query plan output (`--json`) for Claude Code agent integration
- [x] **VAL-01**: `discolike validate` command wrapping `/validate/icp` — score domains against ICP description — Phase 2
- [x] **VAL-02**: Async task polling with progress display for validation jobs — Phase 2
- [x] **VAL-03**: Integration with discover output — pipe discovery results directly to validation — Phase 2
- [x] **GEN-01**: `discolike discogen` command wrapping `/discogen/process` — run LLM prompts against domains — Phase 2
- [x] **GEN-02**: `discolike discogen personas` wrapping `/discogen/process-personas` — LLM prompts against contacts — Phase 2
- [x] **GEN-03**: Async task management (status polling, cancel, interim results display) — Phase 2
- [x] **GEN-04**: Context mode selection (`website`, `profile`, `domain`) — Phase 2
- [x] **GEN-05**: BYOM support — `discolike llm-providers` config commands — Phase 2
- [x] **GEN-06**: BYOS support — `discolike search-providers` config commands — Phase 2
- [ ] **SEG-01**: `discolike segment` command wrapping `/segment` — auto-cluster domains
- [ ] **SEG-02**: CSV/file input for bulk segmentation
- [ ] **SEG-03**: Async task polling with segment results display
- [ ] **SKILL-01**: Interactive multi-dimensional discovery skill in `lg-research/skills/`
- [ ] **SKILL-02**: Seed analysis phase — extract what they sell, who they sell to, industry, size, geo from seed domains
- [ ] **SKILL-03**: Dimension weighting — guide user to tighten/loosen each discovery dimension
- [ ] **SKILL-04**: Query construction → OLM feedback loop → refinement cycle
- [ ] **SKILL-05**: Post-discovery pipeline — optional validate → enrich → segment flow

### Out of Scope

- History endpoint (`/history`) — SSL cert history is niche, low ROI for discovery workflows
- Metrics endpoint (`/metrics`) — aggregated domain metrics, can add later if needed
- Redirects endpoint (`/redirects`) — redirect chain data, minimal discovery value
- PublicLink endpoint (`/publiclink`) — Enterprise-only, we're on Starter/Pro
- Self-hosting (BYOM/BYOS infrastructure) — we use hosted DiscoLike, not self-hosted
- Contact Bulk Match — batch version of existing `match`, add if demand emerges
- MCP server changes — CLI is the interface, MCP is DiscoLike's concern

## Context

- **Existing CLI**: Production-ready Python/Click CLI at `discolike-cli/`, pip-installable, full test coverage
- **API reference**: Complete docs indexed at `leadgrow-hq/archive/mcp-docs/DiscoLike_API_Reference.md` (40+ pages, all endpoints)
- **Existing skill**: `lg-research/skills/discolike-discovery/SKILL.md` — 8-step MCP-based discovery workflow, needs upgrade to use CLI + new capabilities
- **BYOM already configured**: OpenAI API key and Serper dev key are in DiscoLike account — DiscoGen ready to use
- **OLM feedback loop**: Announced by DiscoLike but not as dedicated endpoints. We build it from existing primitives: `X-Applied-Filters` response header + `auto_icp_text`/`auto_phrase_match` flags + explicit param resubmission
- **Plan**: Currently on Starter/Pro — some features (segment) require Pro+
- **Architecture**: Python 3.11+, Click, httpx, Rich, Pydantic v2, SQLite cache, pytest + respx

## Constraints

- **API**: Build against documented endpoints only — no undocumented/beta endpoints
- **Async operations**: DiscoGen, Validate ICP, and Segment are all async (task_id → poll → results). Need consistent async task management pattern
- **Rate limits**: 5 req/min on discover (Starter), 2 req/min on segment. Feedback loop iterations consume quota
- **Cost awareness**: Every API call costs money. Feedback loop iterations should be explicit about cumulative cost
- **Backwards compatibility**: Existing `discover` command behavior unchanged without `--confirm` flag

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build feedback loop from existing API primitives (`X-Applied-Filters` + resubmit) | No dedicated OLM endpoints in docs. Existing primitives give us what we need | — Pending |
| `--confirm` flag on discover (opt-in feedback loop) | Preserve one-shot default for scripts/automation, interactive loop when wanted | — Pending |
| Shared async task manager for DiscoGen/Validate/Segment | All three use task_id → poll pattern. DRY the polling/progress/cancel logic | — Pending |
| Skill lives in `lg-research/skills/` alongside existing `discolike-discovery` | Same domain, same plugin namespace | — Pending |
| Multi-dimensional seed analysis via BizData + Extract | Use existing enrichment endpoints to decompose seed domains before building query | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-08 after Phase 1 completion*
