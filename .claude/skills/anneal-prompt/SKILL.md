---
name: anneal-prompt
description: >
  Optimize an underperforming prompt using the anneal loop. Takes a prompt that
  produces inconsistent or low-quality outputs on a cheap model (Haiku), runs
  iterative optimization with mutation diversity constraints, and graduates a
  prompt hitting 92%+ accuracy. Works as guided flow (human-in-the-loop) or
  autonomous (subagent). Invoke with /anneal-prompt or say "anneal this prompt."
triggers:
  - anneal this prompt
  - this prompt isn't working
  - optimize this prompt
  - prompt is falling short
  - make this prompt better
  - prompt optimization
  - anneal loop
  - cheap model optimization
  - prompt needs improvement
version: 2.0.0
maturity: validated
---

# Anneal Prompt

Optimizes prompts for cheap models (Haiku) to match expensive model (Opus) quality on specific, defined tasks.

**Read `METHODOLOGY.md` in this repo before running.** It defines the mutation diversity rules that prevent the optimizer from gaming its own test set.

## Prerequisites

- Claude Code (CLI, desktop, or IDE extension)
- Bun runtime (`bun --version`)
- This repo cloned locally

## Two Modes

### Mode 1: Guided (human-in-the-loop)

Use when you want to review outputs and steer the optimization.

### Mode 2: Autonomous (subagent)

Use when you want to hand off the optimization and get results back. Spawns from the main session when a prompt is underperforming.

---

## Step 1: Define or Identify the Scenario

**If starting fresh:**

```bash
bun setup.mjs --name [scenario-name]
```

Options:
- `--description "What this prompt does"`
- `--dimensions "accuracy:0.5,format:0.3,style:0.2"` (rubric dimensions with weights)
- `--threshold 0.92` (accuracy target)
- `--budget 800` (max prompt tokens)
- `--iterations 10` (default loop count)

This scaffolds `scenarios/[name]/` with all required directories and templates.

**If resuming an existing scenario:**

Read `scenarios/[name]/evals/loop-state.json` to check current state.

## Step 2: Prepare Test Data

### Inputs (minimum 12, recommended 15)

Create one JSON file per test case in `scenarios/[name]/inputs/`:

```json
{
  "company_name": "Acme Corp",
  "description": "Acme manufactures industrial widgets for automotive OEMs..."
}
```

The input schema depends on your task. These are the real-world cases the prompt must handle.

**Selection criteria:**
- Include the cases where the prompt currently fails (that's why you're here)
- Include easy cases too (to catch regressions)
- Include edge cases (unusual inputs, boundary conditions)
- Represent the real-world distribution, not just the happy path

### Ground Truth (Opus-generated, human-validated)

For each input, create a matching file in `scenarios/[name]/ground-truth/`:

```json
{
  "id": "acme-corp",
  "split": "train",
  "input": { "company_name": "Acme Corp", "description": "..." },
  "ground_truth": { "field1": "expected value", "field2": "expected value" }
}
```

**Generating ground truth:**
1. Run each input through Opus with a detailed version of the task prompt
2. Human reviews every output — correct anything wrong
3. This IS the quality bar. If ground truth is wrong, the optimizer optimizes toward wrong.

**Assigning splits:**
| Split | % | Purpose | When Scored |
|---|---|---|---|
| `train` | 60% | Failures here drive mutations | Every iteration |
| `val` | 30% | Generalization signal | Every iteration |
| `holdout` | 10% | Final exam — never seen during loop | Graduation only |

Holdout must include at least 1 "hard" case that doesn't map to any worked example.

### Baseline Prompt

Paste your current prompt into `scenarios/[name]/prompts/v001.md`. This is the starting point.

## Step 3: Run Baseline (Human Reviews)

Execute v001 against all inputs:

```bash
bun scenarios/[name]/evals/run-eval.mjs --version v001
```

**Show the raw output table:**

| Input | Output | Ground Truth | Score |
|---|---|---|---|
| Acme Corp | [what Haiku produced] | [what's expected] | 0.XX |

Review the outputs. Note:
- Which inputs failed and why
- Whether the rubric dimensions are right
- Whether the ground truth needs adjustment

This is the last human checkpoint before autonomous mode.

## Step 4: Run the Anneal Loop

**Guided:** Run one iteration at a time, review outputs, steer.

**Autonomous:** Say "go iterate" or spawn the loop to run all 10 iterations.

### What happens each iteration:

1. **Analyze failures** — structured patterns with frequency and severity
2. **Select mutation type** — subject to phase constraints:

| Phase | Iterations | Rules |
|---|---|---|
| Bootstrap | 1-3 | Examples allowed, teach the basic pattern |
| Generalize | 4-7 | **Examples blocked.** Structural reasoning only. |
| Polish | 8-10 | Subtractive encouraged. Remove noise, verify. |

3. **Generate mutated prompt** — targeting the priority failure
4. **Execute and score** — against train + val inputs
5. **Show raw output table** — non-negotiable, every iteration
6. **Check halt conditions** — threshold, overfitting, convergence, token budget

### Mutation Diversity Rules (hard constraints)

- **Max 4 examples per concept.** Beyond that = lookup table.
- **No 2 consecutive example-heavy mutations.**
- **Iterations 4-7: NO new examples.** Fix reasoning, not memorization.
- **Iteration 8: subtractive check.** Remove 50% of examples. If score drops < 0.05, keep the lean version.

### Halt Conditions

| Condition | Trigger | Meaning |
|---|---|---|
| Threshold reached | val >= 0.92 | Success |
| Max iterations | iteration >= max | Time's up |
| Convergence plateau | 3 consecutive val deltas < 0.02 | Stuck |
| Overfitting | train-val gap > threshold | Memorizing |
| Token budget | tokens > budget | Prompt too long |

## Step 5: Graduate

When the loop halts with `threshold-reached`:

1. Score best version against **holdout set**
2. Compute generalization metrics:
   - **Val-Train Gap** (healthy: -0.05 to +0.05)
   - **Holdout-Val Gap** (healthy: > -0.08)
   - **Example Density** (healthy: < 0.01 examples/token)
   - **Structural Ratio** (healthy: structural mutations / total > 0.40)
3. If holdout-val gap < -0.10: **do not graduate** (overfitted)
4. Otherwise: write to `library/[scenario].md` with YAML frontmatter

## Example: Real Results

### ICP Classification (4 iterations, val 0.925)

Task: Classify a company for B2B outbound lead gen fit.

```
v001 (baseline)  -> val 0.622  | 267 tokens
v002 (additive)  -> val 0.640  | 295 tokens
v003 (additive)  -> val 0.640  | 340 tokens
v004 (consolid.) -> val 0.925  | 388 tokens  <- graduated
```

Key insight: Consolidation mutation (merging verbose rules into crisp ones) produced the biggest single jump.

### Prospect Identification (9 iterations, val 0.928)

Task: Given a company description, identify their ideal customer business types and decision maker titles.

```
v001 (baseline)     -> val 0.563  | 364 tokens
v002 (additive)     -> val 0.583  | 420 tokens  | +reasoning step
v003 (consolidation)-> val 0.644  | 467 tokens  | +negative example
v004 (targeted)     -> val 0.841  | 509 tokens  | +budget-holder examples  <- breakthrough
v005 (additive)     -> val 0.794  | 604 tokens  | +train examples (val dipped)
v006 (targeted)     -> val 0.806  | 668 tokens  | +M&A example
v007 (targeted)     -> val 0.863  | 695 tokens  | +CIO/logistics fixes
v008 (targeted)     -> val 0.906  | 683 tokens  | +packaging refinement
v009 (consolidation)-> val 0.928  | 648 tokens  | mirror rule  <- graduated
```

Key insight: 60% of mutations were example-based, which drove scores up but risks memorization. This is why METHODOLOGY.md now enforces the generalize phase (iterations 4-7 block examples). The biggest generalizable gain came from structural reframes (v003's buyer-not-seller, v009's mirror rule), not examples.

## Files Reference

| File | Purpose |
|---|---|
| `setup.mjs` | Scaffold new scenarios |
| `METHODOLOGY.md` | Mutation diversity rules, generalization safeguards |
| `scenarios/[name]/scenario.json` | Rubric, thresholds, config |
| `scenarios/[name]/inputs/*.json` | Test case inputs |
| `scenarios/[name]/ground-truth/*.json` | Expert reference outputs with splits |
| `scenarios/[name]/prompts/vNNN.md` | Prompt versions |
| `scenarios/[name]/evals/loop-state.json` | Loop tracking and score history |
| `scenarios/[name]/evals/vNNN-raw.json` | Raw model outputs per iteration |
| `scenarios/[name]/evals/vNNN.json` | Scored results per iteration |
| `library/[name].md` | Graduated prompts with accuracy metadata |
