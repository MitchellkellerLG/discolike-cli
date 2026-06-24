# Interface Depth Analysis

Analysis of each major module: public interface size vs internal implementation depth.

## Summary Table

| Module | Public Functions/Classes | Internal Functions/Classes | Depth Ratio | Verdict |
|--------|--------------------------|---------------------------|-------------|---------|
| `client.py` | 20 (public methods on DiscoLikeClient + 1 class) | 5 (_request, _get_with_params, _get_list, _post_json, _get_cached, _set_cached + 3 module-level privates) | ~0.45 | SHALLOW (inverted — many public methods) |
| `cost.py` | 7 (CostTracker + 5 public methods + 2 properties) | 1 (_check_budget) | 0.14 | SHALLOW |
| `cache.py` | 12 (CacheManager + 11 public methods) | 1 (_init_tables) | 0.08 | SHALLOW |
| `errors.py` | 9 (7 error classes + handle_errors + DiscoLikeError base) | 0 | 0 | SHALLOW |
| `output.py` | 6 (OutputManager + 4 status methods + render + click_echo_json) | 5 (_render_json, _render_table, _render_csv, _render_cost_footer, _extract_records) | 0.83 | ADEQUATE |
| `types.py` | 17 (all Pydantic models) | 0 | 0 | SHALLOW (data only — expected) |
| `config.py` | 5 (get_config_dir, get_config_path, load_config, save_config, get_api_key, mask_key) | 0 | 0 | SHALLOW |
| `constants.py` | all (pure constants + PlanPricing NamedTuple) | 0 | 0 | SHALLOW (expected for constants) |
| `async_tasks.py` | 4 (AsyncTaskManager + poll, cancel, resume, list_tasks) | 0 | 0 | SHALLOW |
| `domain_input.py` | 2 (read_domains, validate_domain_count) | 3 (_parse_text, _parse_csv, _read_stdin) | 1.5 | ADEQUATE |
| `commands/discover.py` | 4 (discovery_filters, collect_filters, count, discover) | 0 | 0 | SHALLOW |
| `commands/plan_gate.py` | 1 (require_plan) | 1 (decorator/wrapper closure) | 1.0 | ADEQUATE |
| `commands/workflow.py` | 3 (workflow group + discover + enrich-list) | 1 (_show_running_cost) | 0.33 | SHALLOW |

---

## Module-by-Module Detail

### `src/discolike/client.py`
- **Public interface:** `DiscoLikeClient` class with 20 public methods covering every API endpoint. Plus `close()`, `__enter__`, `__exit__`, `cost_tracker` and `cache` properties.
- **Internal:** `_request`, `_get_with_params`, `_get_list`, `_post_json`, `_get_cached`, `_set_cached` (6 private methods). Plus module-level `_filters_to_params`, `_parse_account_status`, `_parse_retry_after`.
- **Verdict: SHALLOW** — the class surface is very wide. Each endpoint is its own public method. Callers must know 20+ method names. The hidden complexity is minimal (retry logic lives in `_request`), which is the one well-encapsulated piece.

### `src/discolike/cost.py`
- **Public interface:** `CostTracker` with `record_call`, `estimate`, `set_plan`, plus `plan`, `last_call`, `session_total`, `session_calls` properties.
- **Internal:** `_check_budget` only.
- **Verdict: SHALLOW** — budget check logic is not hidden behind the interface; `record_call` directly calls `_check_budget` with no intermediate policy layer.

### `src/discolike/cache.py`
- **Public interface:** `CacheManager` with 11 public methods across three domains (cache TTL, cost persistence, task persistence).
- **Internal:** `_init_tables` only.
- **Verdict: SHALLOW** — three separate responsibilities (data cache, cost log, task state) are merged into one class with 11 public methods. No separation of concerns.

### `src/discolike/output.py`
- **Public interface:** `OutputManager` with `render`, `status`, `success`, `warning`, `error`. Plus `is_tty` property and module-level `click_echo_json`.
- **Internal:** `_render_json`, `_render_table`, `_render_csv`, `_render_cost_footer`, `_extract_records`.
- **Verdict: ADEQUATE** — `render()` is a clean single-method surface that dispatches internally. The private methods handle the three output modes. `_extract_records` normalizes inputs. This module has the best encapsulation in the codebase.

### `src/discolike/async_tasks.py`
- **Public interface:** `AsyncTaskManager` with `poll`, `cancel`, `resume`, `list_tasks`.
- **Internal:** none (all logic is inside the public methods).
- **Verdict: SHALLOW** — poll logic (interval stepping, timeout calculation, status dispatch) lives directly in the public `poll()` method body with no extraction into private helpers.

### `src/discolike/domain_input.py`
- **Public interface:** `read_domains`, `validate_domain_count`.
- **Internal:** `_parse_text`, `_parse_csv`, `_read_stdin`.
- **Verdict: ADEQUATE** — two-method public interface dispatches internally to three format parsers. Clean pattern.

### `src/discolike/commands/discover.py`
- **Public interface:** `discovery_filters` decorator, `collect_filters` function, `count` command, `discover` command.
- **Internal:** `_FILTER_MAP`, `_SKIP_DEFAULTS` module constants. No private functions.
- **Verdict: SHALLOW** — `collect_filters` and `_FILTER_MAP` encode the same mapping in two representations. The filter assembly logic is exposed as a public function (callers can see and depend on internal mapping logic).
