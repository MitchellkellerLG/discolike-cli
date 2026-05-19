"""HTTP client for the DiscoLike API with retry, caching, and cost tracking."""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Any

import httpx

from discolike.cache import CacheManager
from discolike.config import get_api_key
from discolike.constants import (
    API_BASE_URL,
    AUTH_HEADER,
    CACHE_TTL_ACCOUNT_STATUS,
    CACHE_TTL_EXTRACT,
    CACHE_TTL_PROFILE,
    CACHE_TTL_SCORE,
)
from discolike.cost import CostTracker
from discolike.errors import APIError, AuthError, RateLimitError
from discolike.types import (
    AccountStatus,
    BusinessProfile,
    CountResult,
    DiscoverResult,
    ExtractResult,
    GrowthResult,
    SavedQuery,
    ScoreResult,
    UsageStats,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds


class DiscoLikeClient:
    """HTTP client for all DiscoLike API endpoints.

    All endpoints use GET with query params except /queries/exclusion-list (POST).
    Integrates CostTracker and CacheManager. Supports dry_run mode.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = API_BASE_URL,
        cache: CacheManager | None = None,
        cost_tracker: CostTracker | None = None,
        dry_run: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key or get_api_key()
        self._base_url = base_url.rstrip("/")
        self._cache = cache
        self._cost = cost_tracker or CostTracker()
        self._dry_run = dry_run
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={AUTH_HEADER: self._api_key},
            timeout=self._timeout,
        )

    @property
    def cost_tracker(self) -> CostTracker:
        return self._cost

    @property
    def cache(self) -> CacheManager | None:
        return self._cache

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> DiscoLikeClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- Internal HTTP helpers ---

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry and exponential backoff."""
        url = path
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                if method.upper() == "GET":
                    resp = self._client.get(url, params=params)
                elif method.upper() == "DELETE":
                    resp = self._client.delete(url)
                else:
                    resp = self._client.post(url, json=json_body)

                if resp.status_code == 401:
                    raise AuthError("Invalid or expired API key.")
                if resp.status_code == 429:
                    retry_after = _parse_retry_after(resp)
                    if attempt < MAX_RETRIES - 1:
                        wait = retry_after if retry_after else BACKOFF_BASE * (2**attempt)
                        logger.debug(
                            "Rate limited (attempt %d/%d), waiting %.1fs",
                            attempt + 1,
                            MAX_RETRIES,
                            wait,
                        )
                        time.sleep(wait)
                        continue
                    raise RateLimitError(
                        "Rate limited after max retries.",
                        retry_after=retry_after,
                    )
                if resp.status_code >= 500:
                    if attempt < MAX_RETRIES - 1:
                        wait = BACKOFF_BASE * (2**attempt)
                        logger.debug(
                            "Server error %d (attempt %d/%d), retrying in %.1fs",
                            resp.status_code,
                            attempt + 1,
                            MAX_RETRIES,
                            wait,
                        )
                        time.sleep(wait)
                        continue
                    raise APIError(
                        f"Server error {resp.status_code} after {MAX_RETRIES} retries."
                    )
                if resp.status_code >= 400:
                    raise APIError(
                        f"API error {resp.status_code}: {resp.text}"
                    )

                return resp

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    wait = BACKOFF_BASE * (2**attempt)
                    logger.debug(
                        "Connection error (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                    )
                    time.sleep(wait)
                    continue
                raise APIError(
                    f"Connection failed after {MAX_RETRIES} retries: {exc}"
                ) from exc

        raise APIError(f"Request failed after {MAX_RETRIES} retries.") from last_exc

    def _get_with_params(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """GET request with query params, return parsed JSON."""
        resp = self._request("GET", path, params=params)
        data: dict[str, Any] = resp.json()
        return data

    def _get_list(
        self, path: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """GET request expecting a JSON array response."""
        resp = self._request("GET", path, params=params)
        result: list[dict[str, Any]] = resp.json()
        return result

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST request with JSON body, return parsed JSON."""
        resp = self._request("POST", path, json_body=body)
        data: dict[str, Any] = resp.json()
        return data

    # --- Cached helpers ---

    def _get_cached(self, cache_key: str, ttl: int) -> dict[str, Any] | None:
        """Check cache for a key. Returns parsed dict or None."""
        if self._cache is None:
            return None
        raw = self._cache.get(cache_key, ttl)
        if raw is not None:
            result: dict[str, Any] = json.loads(raw)
            return result
        return None

    def _set_cached(
        self, cache_key: str, data: dict[str, Any], category: str
    ) -> None:
        """Store a value in cache."""
        if self._cache is not None:
            self._cache.set(cache_key, json.dumps(data), category)

    # --- Public API methods ---
    # All endpoints are GET with query params except /queries/exclusion-list

    def account_status(self) -> AccountStatus:
        """GET /usage -> AccountStatus."""
        cache_key = "account_status"
        cached = self._get_cached(cache_key, CACHE_TTL_ACCOUNT_STATUS)
        if cached is not None:
            return _parse_account_status(cached)

        if self._dry_run:
            self._cost.estimate("usage", 0)
            return AccountStatus()

        data = self._get_with_params("/usage")
        self._cost.record_call("usage", 0)
        self._set_cached(cache_key, data, "account")

        result = _parse_account_status(data)
        if result.plan:
            budget = (
                Decimal(str(data.get("total_available_spend", 0)))
                if data.get("total_available_spend")
                else None
            )
            self._cost.set_plan(result.plan, budget)

        return result

    def usage(self) -> UsageStats:
        """GET /usage -> UsageStats (usage portion only)."""
        status = self.account_status()
        return status.usage or UsageStats()

    def extract(self, domain: str) -> ExtractResult:
        """GET /extract?url=<domain> -> ExtractResult."""
        cache_key = f"extract:{domain}"
        cached = self._get_cached(cache_key, CACHE_TTL_EXTRACT)
        if cached is not None:
            return ExtractResult.model_validate(cached)

        if self._dry_run:
            self._cost.estimate("extract", 0)
            return ExtractResult(domain=domain)

        data = self._get_with_params("/extract", {"url": domain})
        self._cost.record_call("extract", 0)
        # API returns {language, text, links} — normalize to include domain
        data["domain"] = domain
        self._set_cached(cache_key, data, "extract")
        return ExtractResult.model_validate(data)

    def count(self, filters: dict[str, Any]) -> CountResult:
        """GET /count?<filters> -> CountResult."""
        if self._dry_run:
            self._cost.estimate("count", 0)
            return CountResult(count=0)

        params = _filters_to_params(filters)
        data = self._get_with_params("/count", params)
        self._cost.record_call("count", 0)
        return CountResult.model_validate(data)

    def discover(
        self,
        filters: dict[str, Any],
        max_records: int = 25,
        fields: list[str] | None = None,
        exclude_query_id: str | None = None,
    ) -> DiscoverResult:
        """GET /discover?<filters>&max_records=N -> DiscoverResult."""
        if self._dry_run:
            self._cost.estimate("discover", max_records)
            return DiscoverResult()

        params = _filters_to_params(filters)
        params["max_records"] = str(max_records)
        if fields:
            params["fields"] = ",".join(fields)
        if exclude_query_id:
            params["exclusion_query_id"] = exclude_query_id

        resp = self._request("GET", "/discover", params=params)
        raw = resp.json()
        # API returns a list of records directly, not {"records": [...]}
        if isinstance(raw, list):
            records = raw
            data = {"records": records, "count": len(records)}
        else:
            data = raw
            records = data.get("records", [])
        self._cost.record_call("discover", len(records))
        return DiscoverResult.model_validate(data)

    def business_profile(
        self, domain: str, fields: list[str] | None = None
    ) -> BusinessProfile:
        """GET /bizdata?domain=<domain> -> BusinessProfile."""
        cache_key = f"profile:{domain}"
        cached = self._get_cached(cache_key, CACHE_TTL_PROFILE)
        if cached is not None:
            return BusinessProfile.model_validate(cached)

        if self._dry_run:
            self._cost.estimate("bizdata", 0)
            return BusinessProfile(domain=domain)

        params: dict[str, Any] = {"domain": domain}
        if fields:
            params["fields"] = ",".join(fields)

        data = self._get_with_params("/bizdata", params)
        self._cost.record_call("bizdata", 0)
        self._set_cached(cache_key, data, "profile")
        return BusinessProfile.model_validate(data)

    def score(self, domain: str) -> ScoreResult:
        """GET /score?domain=<domain> -> ScoreResult."""
        cache_key = f"score:{domain}"
        cached = self._get_cached(cache_key, CACHE_TTL_SCORE)
        if cached is not None:
            return ScoreResult.model_validate(cached)

        if self._dry_run:
            self._cost.estimate("score", 0)
            return ScoreResult(domain=domain)

        data = self._get_with_params("/score", {"domain": domain})
        self._cost.record_call("score", 0)
        self._set_cached(cache_key, data, "score")
        return ScoreResult.model_validate(data)

    def growth(self, domain: str) -> GrowthResult:
        """GET /growth?domain=<domain> -> GrowthResult."""
        if self._dry_run:
            self._cost.estimate("growth", 0)
            return GrowthResult(domain=domain)

        data = self._get_with_params("/growth", {"domain": domain})
        self._cost.record_call("growth", 0)
        return GrowthResult.model_validate(data)

    def saved_queries(self) -> list[SavedQuery]:
        """GET /queries/saved -> list[SavedQuery]."""
        if self._dry_run:
            self._cost.estimate("queries/saved", 0)
            return []

        resp = self._request("GET", "/queries/saved")
        data = resp.json()
        self._cost.record_call("queries/saved", 0)
        if isinstance(data, list):
            return [SavedQuery.model_validate(item) for item in data]
        return []

    def save_exclusion(self, name: str, domains: list[str]) -> SavedQuery:
        """POST /queries/exclusion-list -> SavedQuery."""
        if self._dry_run:
            self._cost.estimate("queries/exclusion-list", 0)
            return SavedQuery(query_name=name)

        data = self._post_json(
            "/queries/exclusion-list",
            {"query_name": name, "domains": domains},
        )
        self._cost.record_call("queries/exclusion-list", 0)
        return SavedQuery.model_validate(data)

    def contacts(
        self, domain: str, title: str | None = None, max_records: int = 25
    ) -> dict[str, Any]:
        """GET /contacts?domain=<domain> -> dict."""
        if self._dry_run:
            self._cost.estimate("contacts", max_records)
            return {}

        params: dict[str, Any] = {
            "domain": domain,
            "max_records": str(max_records),
        }
        if title:
            params["title"] = title

        data = self._get_with_params("/contacts", params)
        self._cost.record_call("contacts", len(data.get("records", [])))
        return data

    def match(self, company_name: str) -> dict[str, Any]:
        """GET /match?name=<company_name> -> dict."""
        if self._dry_run:
            self._cost.estimate("match", 0)
            return {}

        data = self._get_with_params("/match", {"name": company_name})
        self._cost.record_call("match", 0)
        return data

    def append(
        self, domains: list[str], fields: list[str]
    ) -> list[dict[str, Any]]:
        """POST /append -> bulk firmographic data append.

        Sends all domains in a single POST request with JSON body.
        Returns a list of profile dicts keyed by domain.
        """
        if self._dry_run:
            self._cost.estimate("append", len(domains))
            return []

        data = self._post_json(
            "/append",
            {"domains": domains, "fields": fields},
        )
        records = data.get("results", data.get("records", []))
        self._cost.record_call("append", len(records))
        return records

    def vendors(self, domain: str) -> dict[str, Any]:
        """GET /vendors?domain=<domain> -> dict."""
        if self._dry_run:
            self._cost.estimate("vendors", 0)
            return {}

        data = self._get_with_params("/vendors", {"domain": domain})
        self._cost.record_call("vendors", 0)
        return data

    def subsidiaries(self, domain: str) -> dict[str, Any]:
        """GET /subsidiaries?domain=<domain> -> dict."""
        if self._dry_run:
            self._cost.estimate("subsidiaries", 0)
            return {}

        data = self._get_with_params("/subsidiaries", {"domain": domain})
        self._cost.record_call("subsidiaries", 0)
        return data

    def contact_match(
        self, name: str, company: str | None = None
    ) -> dict[str, Any]:
        """GET /contacts/match?name=<name>&company=<company> -> dict."""
        if self._dry_run:
            self._cost.estimate("contacts/match", 0)
            return {}

        params: dict[str, Any] = {"name": name}
        if company:
            params["company"] = company
        data = self._get_with_params("/contacts/match", params)
        self._cost.record_call("contacts/match", 0)
        return data

    def contact_bulk_match(
        self, names: list[dict[str, str]]
    ) -> dict[str, Any]:
        """POST /contacts/bulk-match -> bulk contact lookup.

        Args:
            names: List of {"name": "...", "company": "..." (optional)} dicts.
        """
        if self._dry_run:
            self._cost.estimate("contacts/bulk-match", len(names))
            return {}

        data = self._post_json("/contacts/bulk-match", {"contacts": names})
        self._cost.record_call(
            "contacts/bulk-match", len(data.get("results", []))
        )
        return data

    def bulk_match(self, names: list[str]) -> dict[str, Any]:
        """POST /match/bulk -> bulk company name -> domain matching."""
        if self._dry_run:
            self._cost.estimate("match/bulk", len(names))
            return {}

        data = self._post_json("/match/bulk", {"names": names})
        self._cost.record_call(
            "match/bulk", len(data.get("results", []))
        )
        return data

    def llm_providers_list(self) -> dict[str, Any]:
        """GET /llm-providers/config -> list configured LLM providers."""
        if self._dry_run:
            self._cost.estimate("llm-providers", 0)
            return {}

        data = self._get_with_params("/llm-providers/config")
        self._cost.record_call("llm-providers", 0)
        return data

    def llm_providers_set(
        self, provider: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /llm-providers/config -> create/update LLM provider config."""
        if self._dry_run:
            self._cost.estimate("llm-providers", 0)
            return {}

        data = self._post_json(
            "/llm-providers/config", {"provider": provider, **config}
        )
        self._cost.record_call("llm-providers", 0)
        return data

    def search_providers_list(self) -> dict[str, Any]:
        """GET /search-providers -> list configured search providers."""
        if self._dry_run:
            self._cost.estimate("search-providers", 0)
            return {}

        data = self._get_with_params("/search-providers")
        self._cost.record_call("search-providers", 0)
        return data

    def search_providers_set(
        self, provider: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /search-providers -> update search provider config.

        API expects: integration_name, provider, search_model, api_key.
        """
        if self._dry_run:
            self._cost.estimate("search-providers", 0)
            return {}

        body = {
            "integration_name": config.get("integration_name", provider),
            "provider": provider,
            "search_model": config.get("search_model", "default"),
            "api_key": config.get("api_key", ""),
        }
        data = self._post_json("/search-providers", body)
        self._cost.record_call("search-providers", 0)
        return data

    # --- Async task methods ---

    def discogen_submit(self, params: dict[str, Any]) -> dict[str, Any]:
        """POST /discogen/process -> raw response dict including task_id."""
        if self._dry_run:
            self._cost.estimate("discogen", 0)
            return {"task_id": "dry-run-task-id", "status": "in_progress"}
        return self._post_json("/discogen/process", params)

    def discogen_personas_submit(self, params: dict[str, Any]) -> dict[str, Any]:
        """POST /discogen/process-personas -> raw response dict including task_id."""
        if self._dry_run:
            self._cost.estimate("discogen-personas", 0)
            return {"task_id": "dry-run-task-id", "status": "in_progress"}
        return self._post_json("/discogen/process-personas", params)

    def validate_icp_submit(self, params: dict[str, Any]) -> dict[str, Any]:
        """POST /validate/icp -> raw response dict including task_id."""
        if self._dry_run:
            self._cost.estimate("validate/icp", 0)
            return {"task_id": "dry-run-task-id", "status": "in_progress"}
        return self._post_json("/validate/icp", params)

    def segment_submit(self, params: dict[str, Any]) -> dict[str, Any]:
        """POST /segment -> raw response dict including task_id."""
        if self._dry_run:
            self._cost.estimate("segment", 0)
            return {"task_id": "dry-run-task-id", "status": "in_progress"}
        return self._post_json("/segment", params)

    def task_status(self, task_id: str) -> dict[str, Any]:
        """GET /discogen/status/{task_id} -> status dict.

        Note: All async endpoints (DiscoGen, Validate ICP, Segment) share
        /discogen/status/ for polling. The task_id is globally unique.
        """
        return self._get_with_params(f"/discogen/status/{task_id}")

    def task_cancel(self, task_id: str) -> dict[str, Any]:
        """DELETE /discogen/cancel/{task_id} -> cancellation confirmation."""
        resp = self._request("DELETE", f"/discogen/cancel/{task_id}")
        result: dict[str, Any] = resp.json()
        return result


def _filters_to_params(filters: dict[str, Any]) -> dict[str, Any]:
    """Convert filter dict to query param dict for GET requests.

    List values pass through as-is so httpx serializes them as repeated
    query keys (e.g. ?category=SAAS&category=SOFTWARE). The DiscoLike API
    validates each list item against an enum, so comma-joining fails.
    Boolean values become lowercase strings.
    """
    params: dict[str, Any] = {}
    for key, val in filters.items():
        if val is None:
            continue
        if isinstance(val, list):
            if not val:
                continue
            params[key] = [str(v) for v in val]
        elif isinstance(val, bool):
            params[key] = str(val).lower()
        else:
            params[key] = str(val)
    return params


def _parse_account_status(data: dict[str, Any]) -> AccountStatus:
    """Parse the flat usage response into AccountStatus + UsageStats."""
    usage = UsageStats(
        month_to_date_requests=data.get("month_to_date_requests"),
        month_to_date_records=data.get("month_to_date_records"),
        month_to_date_spend=(
            Decimal(str(data["month_to_date_spend"]))
            if data.get("month_to_date_spend") is not None
            else None
        ),
        max_spend=(
            Decimal(str(data["max_spend"]))
            if data.get("max_spend") is not None
            else None
        ),
        total_available_spend=(
            Decimal(str(data["total_available_spend"]))
            if data.get("total_available_spend") is not None
            else None
        ),
        carryover_credits=(
            Decimal(str(data["carryover_credits"]))
            if data.get("carryover_credits") is not None
            else None
        ),
        top_up_credits=(
            Decimal(str(data["top_up_credits"]))
            if data.get("top_up_credits") is not None
            else None
        ),
    )
    return AccountStatus(
        account_status=data.get("account_status"),
        plan=data.get("plan"),
        usage=usage,
    )


def _parse_retry_after(resp: httpx.Response) -> float | None:
    """Extract Retry-After header value in seconds."""
    val = resp.headers.get("retry-after")
    if val is not None:
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
    return None
