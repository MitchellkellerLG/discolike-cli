# Deepening Opportunities

Concrete improvement candidates based on interface depth analysis and code review.

---

## 1. `CacheManager` — Three Responsibilities in One Class

**Problem:** `CacheManager` mixes TTL data caching, cost log persistence, and async task state into a single class with 11 public methods. Callers (client.py, cost.py, async_tasks.py) import `CacheManager` for different reasons, and each sees the full 11-method surface.

**Proposed Solution:** Extract into three focused classes behind a thin facade:
- `DataCache` — `get()`, `set()`, `clear()`, `stats()`
- `CostLog` — `record_cost()`, `get_session_costs()`, `get_session_total()`, `reset_costs()`
- `TaskStore` — `save_task()`, `update_task_status()`, `get_task()`, `list_tasks()`

`CacheManager` becomes a facade that owns all three, preserving the existing call sites.

**Impact: HIGH** — improves testability (each concern can be mocked independently), reduces cognitive load when reading client.py or async_tasks.py, and enables independent TTL/eviction strategies per concern.

---

## 2. `DiscoLikeClient` — Wide Public Interface

**Problem:** `DiscoLikeClient` has 20+ public methods, one per API endpoint. This exposes the full API surface to every caller. Commands import the client and must know which of 20 methods to call.

**Proposed Solution:** Group endpoint methods into thin namespaces (not new classes, just grouping by domain):
- `client.discovery.*` — count, discover, extract
- `client.enrichment.*` — business_profile, score, growth
- `client.account.*` — account_status, usage
- `client.async_.*` — discogen_submit, validate_icp_submit, segment_submit, task_status, task_cancel

Alternatively, keep the flat interface but move the 9 async/task methods to `AsyncTaskManager` (which already has client as a dependency). The two methods that belong there (`task_status`, `task_cancel`) are currently on `DiscoLikeClient` even though only `AsyncTaskManager` calls them.

**Impact: MEDIUM** — the grouped approach is a larger refactor; moving task methods to AsyncTaskManager is surgical and immediately reduces the public surface.

---

## 3. `AsyncTaskManager.poll()` — Logic Density

**Problem:** `poll()` contains all interval stepping, timeout checking, status dispatch, and KeyboardInterrupt handling in a single method body (~50 lines). The polling algorithm and the status routing are tangled.

**Proposed Solution:** Extract two private helpers:
- `_compute_next_interval(current: float, step: float, max_val: float) -> float` — pure function, trivially testable
- `_dispatch_status(status: str, result: dict, task_id: str) -> bool | None` — returns True on completion, raises on failure, returns None to continue

This makes the `poll()` main loop a clear skeleton and makes the sub-behaviors unit-testable without needing a full mock client.

**Impact: MEDIUM** — improves testability and readability of the most complex method in the codebase.

---

## 4. `collect_filters` / `_FILTER_MAP` — Leaky Abstraction

**Problem:** `_FILTER_MAP` is a module-level dict exposed implicitly through `collect_filters`. The Click kwarg-to-API-param mapping is scattered across `discovery_filters` (where options are defined), `_FILTER_MAP` (where names are translated), and `_SKIP_DEFAULTS` (where falsy exclusions live). Three data structures encode one policy.

**Proposed Solution:** Define a single `FilterSpec` dataclass per filter:
```python
@dataclass
class FilterSpec:
    click_name: str
    api_name: str
    skip_if_false: bool = False
    skip_if_default: str | None = None
```

A list of `FilterSpec` objects replaces both `_FILTER_MAP` and `_SKIP_DEFAULTS`. The `collect_filters` function iterates one structure instead of two.

**Impact: LOW** — correct behavior unchanged, but the policy is now in one place and easier to audit when the API adds new filter parameters.

---

## 5. `workflow.py` — Sequential Enrichment Loop

**Problem:** `workflow enrich-list` enriches domains in a `for` loop — one API call per domain for each enrichment type. For a list of 100 domains with profile+score+growth, this is 300 sequential HTTP calls. No concurrency, no batching, no progress recovery.

**Proposed Solution:** This is the most natural place to introduce batching via the `/append` endpoint (which accepts multiple domains in one POST). The workflow command already imports from `exporters.csv_export` — the pattern exists. A batch-aware inner loop would reduce HTTP calls from O(n × enrichment_types) to O(n / batch_size × enrichment_types).

Note: this conflicts with ADR-0001's sync-only decision only if async concurrency is used. Batching via `/append` is purely sync.

**Impact: HIGH** — the current sequential loop is the main performance bottleneck for production list enrichment workflows. A 100-domain enrichment takes 300+ network round trips.

---

## 6. Missing Seam: `get_client()` in `cli.py`

**Problem:** `get_client()` is a module-level function in `cli.py` that lazily initializes the client by reaching into `ctx.obj`. Commands import this function directly. There is no seam to inject a test client without monkeypatching `cli.py`.

**Proposed Solution:** Add a `client_factory: Callable[[], DiscoLikeClient] | None = None` parameter to `CliContext`. In tests, set `ctx.obj.client` directly before invoking commands via `CliRunner`. This avoids the monkeypatch and makes test setup explicit.

**Impact: MEDIUM** — affects testability of all command-level tests. Currently tests must mock `get_client` at the module level, which is fragile to import order.
