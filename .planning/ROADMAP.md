# Roadmap: DiscoLike CLI v2 — OLM Feedback Loop & AI Discovery

## Overview

Five phases that transform the one-shot discovery CLI into a closed-loop query refinement system. Phase 1 builds the shared async foundation that every subsequent command depends on. Phases 2 and 3 run independently off that foundation — async commands (Validate + DiscoGen) and the OLM feedback loop are separate delivery boundaries. Phase 4 layers on Segment and provider config. Phase 5 wraps all CLI capabilities into an interactive multi-dimensional discovery skill.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Async Infrastructure** - Shared AsyncTaskManager, SQLite task persistence, and client submit/status/cancel methods for all async endpoints (completed 2026-04-08)
- [ ] **Phase 2: Async Commands** - `discolike validate` and `discolike discogen` commands with async progress, pre-flight cost estimates, and context mode selection
- [ ] **Phase 3: OLM Feedback Loop** - `--confirm` flag on `discover`, QueryPlan display, mutable QueryState, convergence gate, and all cost/safety guards
- [ ] **Phase 4: Segment + Config** - `discolike segment` (Pro+ gated), `discolike llm-providers`, `discolike search-providers`, and `discolike tasks` management
- [ ] **Phase 5: Discovery Skill** - Interactive multi-dimensional discovery skill in lg-research/skills/ wrapping all v2 CLI capabilities

## Phase Details

### Phase 1: Async Infrastructure
**Goal**: All async endpoints (DiscoGen, Validate ICP, Segment) share a single, resilient task lifecycle — jobs survive CLI exit, Ctrl+C prints task_id, polling uses sane backoff
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05
**Success Criteria** (what must be TRUE):
  1. Any async job submitted via CLI writes its task_id to SQLite before first poll — restarting the CLI after Ctrl+C can resume or cancel the job
  2. Ctrl+C during an async poll prints the task_id to stderr and exits cleanly (job continues server-side)
  3. Polling backs off from 3s to a 15s cap and hard-stops at 300s with a timeout error
  4. Client exposes `discogen_submit`, `validate_icp_submit`, `segment_submit`, `task_status`, and `task_cancel` methods
**Plans**: 2 plans
Plans:
- [x] 01-01-PLAN.md -- Foundation: types, errors, cache tasks table, client async methods
- [x] 01-02-PLAN.md -- AsyncTaskManager: poll/cancel/resume lifecycle

### Phase 2: Async Commands
**Goal**: Users can run AI enrichment and ICP validation against domain lists, see live progress, review results in sorted tables, and pipe discovery output directly into validation
**Depends on**: Phase 1
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, GEN-06
**Success Criteria** (what must be TRUE):
  1. `discolike validate --icp "description" --input domains.csv` submits, polls, and displays results sorted by yes+high confidence at top
  2. `discolike discover ... | discolike validate --icp "description"` works end-to-end via stdin pipe
  3. `discolike discogen --prompt "..." --input domains.csv` shows a pre-flight cost estimate (DiscoLike credits + estimated LLM fees) before submission
  4. `discolike discogen personas --prompt "..." --input contacts.csv` runs against contact persona IDs with correct context modes
  5. Interim results appear during long-running DiscoGen jobs — user sees progress before the job completes
**Plans**: 2 plans
Plans:
- [ ] 02-01-PLAN.md -- Shared domain input helper + validate command (VAL-01..04)
- [ ] 02-02-PLAN.md -- DiscoGen command group: run + personas with interim display (GEN-01..06)

### Phase 3: OLM Feedback Loop
**Goal**: Users can review and refine the query plan DiscoLike derived from their seed before committing to a full TAM query — explicit convergence gate, cost visibility, and agent-safe TTY guard throughout
**Depends on**: Phase 1
**Requirements**: LOOP-01, LOOP-02, LOOP-03, LOOP-04, LOOP-05, LOOP-06, LOOP-07, LOOP-08, LOOP-09, LOOP-10
**Success Criteria** (what must be TRUE):
  1. `discolike discover ... --confirm` displays the structured QueryPlan (lookalike text, phrase matches, industry groups, applied filters) after the first call and prompts for adjustments
  2. After the first iteration, resubmission uses only explicit params — the OLM cannot re-derive and overwrite manual corrections
  3. Each resubmission shows cumulative cost (iterations so far + estimated next iteration) before executing
  4. The loop exits only when the user explicitly confirms "run full TAM query" — no silent convergence
  5. Running `--confirm` when stdin is not a TTY raises a UsageError (protects agent/pipe workflows)
  6. `--json` output includes machine-readable query plan so Claude Code agents can participate in the loop
**Plans**: 2 plans
Plans:
- [ ] 03-01-PLAN.md -- [to be planned]
- [ ] 03-02-PLAN.md -- [to be planned]

### Phase 4: Segment + Config
**Goal**: Pro+ users can auto-cluster domain lists into segments, and all users can configure BYOM/BYOS providers and manage in-flight async tasks from the CLI
**Depends on**: Phase 1
**Requirements**: SEG-01, SEG-02, SEG-03, CFG-01, CFG-02, CFG-03
**Success Criteria** (what must be TRUE):
  1. `discolike segment --input domains.csv` on a non-Pro+ account displays a clear upgrade message and exits without submitting
  2. `discolike segment --input domains.csv` on a Pro+ account submits, polls, and displays grouped results with segment descriptions
  3. `discolike llm-providers list/create/update/delete/test/set-default` and `discolike search-providers` equivalents all function correctly
  4. `discolike tasks list` shows in-flight and recent completed tasks; `discolike tasks cancel <task_id>` cancels an orphaned job
**Plans**: 2 plans
Plans:
- [ ] 04-01-PLAN.md -- [to be planned]
- [ ] 04-02-PLAN.md -- [to be planned]

### Phase 5: Discovery Skill
**Goal**: A Claude Code agent can run a complete discovery workflow — seed analysis through validated, enriched, segmented results — guided by an interactive skill that uses all v2 CLI commands
**Depends on**: Phase 2, Phase 3, Phase 4
**Requirements**: SKILL-01, SKILL-02, SKILL-03, SKILL-04, SKILL-05
**Success Criteria** (what must be TRUE):
  1. Skill exists at `lg-research/skills/discolike-discovery-v2/SKILL.md` and is discoverable by smart-searcher
  2. Seed analysis phase extracts what companies sell, who they sell to, industry, size, and geo using BizData + Extract — before any query is constructed
  3. Skill guides user through dimension weighting (tighten vs loosen) for each discovery dimension with concrete CLI flag implications
  4. Skill integrates the OLM feedback loop — runs `discolike discover --confirm`, walks through iterations, confirms convergence
  5. Post-discovery pipeline offers guided steps: optional validate → optional DiscoGen enrichment → optional segment
**Plans**: 2 plans
Plans:
- [ ] 05-01-PLAN.md -- [to be planned]
- [ ] 05-02-PLAN.md -- [to be planned]

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5
Note: Phases 2, 3, and 4 all depend only on Phase 1 — they can be planned in parallel but execute sequentially.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Async Infrastructure | 2/2 | Complete   | 2026-04-08 |
| 2. Async Commands | 0/2 | Planning complete | - |
| 3. OLM Feedback Loop | 0/TBD | Not started | - |
| 4. Segment + Config | 0/TBD | Not started | - |
| 5. Discovery Skill | 0/TBD | Not started | - |
