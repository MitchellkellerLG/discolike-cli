---
phase: 1
slug: async-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + respx (mock httpx) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/test_tasks.py tests/test_client_async.py -v` |
| **Full suite command** | `pytest tests/ -v --cov=discolike` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_tasks.py tests/test_client_async.py -v`
- **After every plan wave:** Run `pytest tests/ -v --cov=discolike`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | INFRA-01 | unit | `pytest tests/test_tasks.py -k "test_async_task_manager"` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | INFRA-02 | unit | `pytest tests/test_tasks.py -k "test_task_persistence"` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | INFRA-05 | unit | `pytest tests/test_tasks.py -k "test_backoff"` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | INFRA-03 | unit | `pytest tests/test_client_async.py -k "test_submit"` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | INFRA-03 | unit | `pytest tests/test_client_async.py -k "test_status_cancel"` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 2 | INFRA-04 | unit+manual | `pytest tests/test_tasks.py -k "test_ctrl_c"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_tasks.py` — stubs for AsyncTaskManager (INFRA-01, INFRA-02, INFRA-04, INFRA-05)
- [ ] `tests/test_client_async.py` — stubs for client submit/status/cancel methods (INFRA-03)
- [ ] `tests/fixtures/task_responses.py` — mock API response shapes for task status, discogen, validate, segment

*Existing test infrastructure (pytest, respx, conftest.py) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Ctrl+C prints task_id to stderr | INFRA-04 | Signal handling is hard to test in pytest without subprocess | Run `discolike discogen --prompt "test" --input test.csv`, press Ctrl+C, verify stderr output contains task_id |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
