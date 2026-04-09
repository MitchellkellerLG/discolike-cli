---
phase: 2
slug: async-commands
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` → `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_validate.py tests/test_discogen.py tests/test_domain_input.py -v` |
| **Full suite command** | `pytest tests/ -v --cov=discolike` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_validate.py tests/test_discogen.py tests/test_domain_input.py -x`
- **After every plan wave:** Run `pytest tests/ -v --cov=discolike`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | VAL-01..04, GEN-01..06 | infra | `pytest tests/conftest.py --collect-only` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | VAL-03 | unit | `pytest tests/test_domain_input.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | VAL-01, VAL-02, VAL-04 | unit | `pytest tests/test_validate.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | GEN-01, GEN-03, GEN-04, GEN-05, GEN-06 | unit | `pytest tests/test_discogen.py -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | GEN-02 | unit | `pytest tests/test_discogen.py::test_discogen_personas -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared CliRunner, respx mock fixtures, fake API responses
- [ ] `tests/test_validate.py` — stubs for VAL-01 through VAL-04
- [ ] `tests/test_discogen.py` — stubs for GEN-01 through GEN-06
- [ ] `tests/test_domain_input.py` — stubs for D-01, D-02, D-03 (file, stdin, inline, CSV, 10k cap)
- [ ] `tests/fixtures/validate_completed.json` — real API response shape for completed validate
- [ ] `tests/fixtures/discogen_interim.json` — in-progress response with interim_results
- [ ] `tests/fixtures/discogen_completed.json` — completed discogen response

*(No existing test infrastructure — tests/ directory is empty.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Ctrl+C during poll prints task_id | INFRA-04 (Phase 1) | Signal handling not testable in pytest | Run `discolike validate ...` and Ctrl+C during poll. Verify task_id in stderr. |
| Rich live table visual rendering | GEN-06 | Visual output quality | Run discogen against real API, observe interim rows appearing |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
