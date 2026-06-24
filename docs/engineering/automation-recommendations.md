# Automation Recommendations

Concrete Claude Code automations that would benefit discolike-cli development.

---

## Pre-Commit Hooks

### 1. Ruff lint check

**What:** Run `ruff check src tests` before every commit.  
**Why:** Catches import order, unused imports, style violations before they hit CI. The codebase already uses `ruff` with a strict ruleset (E, F, I, N, W, UP).  
**Implementation:**
```
# .pre-commit-config.yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  hooks:
    - id: ruff
      args: [--fix]
```

### 2. mypy type check

**What:** Run `mypy src` before commit.  
**Why:** The codebase uses strict mypy with `warn_return_any` and `warn_unused_configs`. New commands added without type annotations silently pass ruff but fail mypy. Catching this pre-commit avoids broken CI.  
**Implementation:**
```
- repo: local
  hooks:
    - id: mypy
      name: mypy
      entry: mypy src
      language: system
      pass_filenames: false
```

### 3. Pytest smoke run (fast subset)

**What:** Run `pytest tests/ -x -q --ignore=tests/test_client.py` before commit (client tests need `respx` mock setup and are slower).  
**Why:** `test_cost.py`, `test_cache.py`, `test_config.py`, and the new `test_domain_input_and_plan_gate.py` run in under 1 second and cover the core business logic. Fast feedback without blocking flow.  
**Implementation:**
```
- repo: local
  hooks:
    - id: pytest-fast
      name: pytest fast suite
      entry: python -m pytest tests/ -x -q --ignore=tests/test_client.py
      language: system
      pass_filenames: false
```

---

## Skills That Would Benefit This Repo

### 4. `tdd` skill

**What:** Bootstrap new test files for untested modules.  
**Why:** Several modules lack test files: `output.py` (only partially tested via integration), `workflow.py`, `append.py`, `segment.py`. The `tdd` skill generates test stubs from the module's public interface.  
**When to invoke:** Any time a new command file is added to `src/discolike/commands/`.

### 5. `code-review` skill

**What:** Static analysis pass before opening a PR.  
**Why:** The wide public interface on `DiscoLikeClient` (20+ methods) means new endpoint methods can accidentally miss cost tracking or cache integration. A review pass catches these before merge.  
**When to invoke:** Before any PR that adds a new client method or command.

---

## Custom Agents for Common Tasks

### 6. `add-endpoint` agent

**What:** A specialized agent prompt for adding a new DiscoLike API endpoint.  
**Why:** Every new endpoint follows the same pattern: add a method to `DiscoLikeClient`, add a command in `commands/`, register it in `cli.py`, add a test fixture, write a test. The pattern is mechanical and error-prone (forgetting cost tracking, missing `@handle_errors`).  
**Implementation sketch:**
```markdown
# prompt: add-endpoint
Task: Add DiscoLike endpoint <name>
1. Add method to DiscoLikeClient (with dry_run + cost tracking)
2. Create commands/<name>.py (with @handle_errors, @click.pass_context)
3. Register in cli.py via cli.add_command()
4. Add fixture to tests/fixtures/<name>.json
5. Write tests/test_<name>.py using respx mock
Verify: mypy src passes, pytest tests/ passes
```

### 7. `release-check` agent

**What:** Pre-release verification agent.  
**Why:** The CLI has 7 exit codes, 5 plan tiers, and 2 async patterns. A release-check agent can run the full test suite, verify `discolike --version` matches `pyproject.toml`, and check that all commands are registered.  
**Implementation sketch:**
```
python -m pytest tests/ -v
python -c "from discolike.cli import cli; print([c.name for c in cli.commands.values()])"
python -c "from discolike import __version__; print(__version__)"
# Compare against pyproject.toml version
```

---

## File Watchers / Background Automations

### 8. `watch-fixtures` background task

**What:** When a test fixture JSON file is updated in `tests/fixtures/`, automatically run the corresponding test file.  
**Why:** Fixture updates (when the DiscoLike API response shape changes) silently break tests. Watching fixtures and running the relevant tests immediately surfaces regressions.  
**Implementation:** Claude Code file watcher on `tests/fixtures/**/*.json` → trigger `pytest tests/test_client.py -v`.

### 9. `constants-sync` check

**What:** Warn when `constants.py` has PLAN_PRICING entries not matching `PLAN_LEVELS`.  
**Why:** `PLAN_LEVELS` and `PLAN_PRICING` must stay in sync — a new plan tier added to one but not the other silently breaks gate checks and dry-run estimates. A simple assertion in a test (or pre-commit hook) that `set(PLAN_PRICING.keys()) == set(PLAN_LEVELS)` catches this.  
**Implementation:** Add `tests/test_constants.py` with a single consistency assertion.
