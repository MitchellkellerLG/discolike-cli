# Requirements: DiscoLike CLI v2

**Defined:** 2026-04-08
**Core Value:** The feedback loop between Claude Code's client context and DiscoLike's search model — both models iterate on the query plan until convergence, then run full TAM queries with confidence.

## v2 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Async Infrastructure

- [ ] **INFRA-01**: Shared AsyncTaskManager handles poll/progress/cancel lifecycle for all async endpoints (DiscoGen, Validate ICP, Segment)
- [ ] **INFRA-02**: SQLite `tasks` table persists task_id before first poll — survives CLI exit, prevents orphaned jobs
- [ ] **INFRA-03**: Client gains submit/status/cancel methods for all async endpoints (`discogen_submit`, `validate_icp_submit`, `segment_submit`, `task_status`, `task_cancel`)
- [ ] **INFRA-04**: Ctrl+C signal handler prints task_id to stderr and persists state before exit
- [ ] **INFRA-05**: Polling uses linear-to-capped backoff (3s initial, 15s max, 300s hard timeout)

### OLM Feedback Loop

- [ ] **LOOP-01**: `discover` command extracts `X-Applied-Filters` response header and parses into structured QueryPlan (lookalike text, phrase matches, industry groups, filters applied)
- [ ] **LOOP-02**: `--confirm` flag on `discover` enables interactive review/adjust/resubmit cycle (opt-in, existing one-shot behavior preserved)
- [ ] **LOOP-03**: After iteration 1, resubmission uses explicit params only — prevents OLM re-derivation from overwriting manual corrections
- [ ] **LOOP-04**: Convergence gate — user or agent explicitly confirms "run full TAM query" before final execution
- [ ] **LOOP-05**: Machine-readable JSON query plan output when `--json` flag is set — enables Claude Code agent-in-the-loop workflows
- [ ] **LOOP-06**: Cumulative cost display before each resubmission showing iteration count, cost so far, and estimated next iteration cost
- [ ] **LOOP-07**: `--max-iterations` flag (default 3) prevents runaway loops in automated contexts
- [ ] **LOOP-08**: Query plan diff view between iterations showing what changed
- [ ] **LOOP-09**: TTY guard — `--confirm` raises UsageError when stdin is not a TTY (protects agent/pipe mode)
- [ ] **LOOP-10**: Mutable QueryState preserves accumulated refinements across iterations (merge-not-replace)

### Validate ICP

- [ ] **VAL-01**: `discolike validate` command accepts ICP text + domain list, submits to `/validate/icp`, polls for results
- [ ] **VAL-02**: Results displayed as sorted action table — yes+high at top, no+high as exclusion candidates
- [ ] **VAL-03**: Pipe integration — accepts domain list from stdin or `--input` file, enabling `discolike discover ... | discolike validate`
- [ ] **VAL-04**: Context mode selection (`website`, `profile`, `domain`) with cost implications displayed

### DiscoGen

- [ ] **GEN-01**: `discolike discogen` command accepts prompt + domain list, submits to `/discogen/process`, polls for results with interim display
- [ ] **GEN-02**: `discolike discogen personas` accepts prompt + persona IDs, submits to `/discogen/process-personas`
- [ ] **GEN-03**: Pre-flight cost estimate showing DiscoLike credits + estimated LLM fees before submission
- [ ] **GEN-04**: Context mode selection (`website`, `profile`, `domain` for domains; `full`, `company`, `profile`, `name_only` for personas)
- [ ] **GEN-05**: `web_search` flag with explicit warning when used on >50 domains (cost multiplier)
- [ ] **GEN-06**: Interim results display during long-running jobs — show progress as results come in

### Segment

- [ ] **SEG-01**: `discolike segment` command accepts CSV/file input, submits to `/segment`, polls for results
- [ ] **SEG-02**: Pro+ plan gate at command entry with clear upgrade message
- [ ] **SEG-03**: Results displayed as grouped table with segment descriptions and domain assignments

### Configuration

- [ ] **CFG-01**: `discolike llm-providers` CRUD — list, create, update, delete, test-connection, set-default
- [ ] **CFG-02**: `discolike search-providers` CRUD — list, create, update, delete, test-connection, set-default
- [ ] **CFG-03**: `discolike tasks` subcommands — list in-flight/completed tasks, check status, cancel orphaned jobs

### Discovery Skill

- [ ] **SKILL-01**: Interactive multi-dimensional discovery skill in `lg-research/skills/discolike-discovery-v2/SKILL.md`
- [ ] **SKILL-02**: Seed analysis phase — use BizData + Extract on seed domains to decompose what they sell, who they sell to, industry, size, geo
- [ ] **SKILL-03**: Dimension weighting guidance — help user decide which dimensions to tighten (narrow) vs loosen (broad) for their use case
- [ ] **SKILL-04**: Query construction → OLM feedback loop integration → iterative refinement cycle using CLI commands
- [ ] **SKILL-05**: Post-discovery pipeline — optional validate → enrich (DiscoGen) → segment flow as guided steps

## v3 Requirements (Deferred)

### Advanced Enrichment

- **ADV-01**: `previous_discogen_data` chaining — iterative multi-pass enrichment
- **ADV-02**: History endpoint (`/history`) — SSL certificate history
- **ADV-03**: Metrics endpoint (`/metrics`) — aggregated domain metrics
- **ADV-04**: Redirects endpoint (`/redirects`) — domain redirect chains
- **ADV-05**: Contact Bulk Match — batch contact resolution

## Out of Scope

| Feature | Reason |
|---------|--------|
| PublicLink endpoint | Enterprise-only, we're on Starter/Pro |
| Self-hosting (BYOM/BYOS infrastructure) | We use hosted DiscoLike |
| MCP server changes | CLI is our interface, MCP is DiscoLike's concern |
| Async/await (asyncio) | Synchronous polling with sleep is simpler and sufficient |
| New interactive prompt library | questionary 2.1.1 covers all needs |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| LOOP-01 | Phase 3 | Pending |
| LOOP-02 | Phase 3 | Pending |
| LOOP-03 | Phase 3 | Pending |
| LOOP-04 | Phase 3 | Pending |
| LOOP-05 | Phase 3 | Pending |
| LOOP-06 | Phase 3 | Pending |
| LOOP-07 | Phase 3 | Pending |
| LOOP-08 | Phase 3 | Pending |
| LOOP-09 | Phase 3 | Pending |
| LOOP-10 | Phase 3 | Pending |
| VAL-01 | Phase 2 | Pending |
| VAL-02 | Phase 2 | Pending |
| VAL-03 | Phase 2 | Pending |
| VAL-04 | Phase 2 | Pending |
| GEN-01 | Phase 2 | Pending |
| GEN-02 | Phase 2 | Pending |
| GEN-03 | Phase 2 | Pending |
| GEN-04 | Phase 2 | Pending |
| GEN-05 | Phase 2 | Pending |
| GEN-06 | Phase 2 | Pending |
| SEG-01 | Phase 4 | Pending |
| SEG-02 | Phase 4 | Pending |
| SEG-03 | Phase 4 | Pending |
| CFG-01 | Phase 4 | Pending |
| CFG-02 | Phase 4 | Pending |
| CFG-03 | Phase 4 | Pending |
| SKILL-01 | Phase 5 | Pending |
| SKILL-02 | Phase 5 | Pending |
| SKILL-03 | Phase 5 | Pending |
| SKILL-04 | Phase 5 | Pending |
| SKILL-05 | Phase 5 | Pending |

**Coverage:**
- v2 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0

---
*Requirements defined: 2026-04-08*
*Last updated: 2026-04-08 after roadmap creation*
