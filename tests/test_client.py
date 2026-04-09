"""Tests for DiscoLikeClient — HTTP client with retry, cache, and cost tracking."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from discolike.cache import CacheManager
from discolike.client import DiscoLikeClient
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
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


@pytest.fixture
def cache(tmp_path: Path) -> CacheManager:
    return CacheManager(db_path=tmp_path / "test.db")


@pytest.fixture
def cost_tracker() -> CostTracker:
    return CostTracker(plan="starter")


@pytest.fixture
def base_url() -> str:
    return "https://test-api.discolike.com/v1"


@pytest.fixture
def client(
    base_url: str, cache: CacheManager, cost_tracker: CostTracker
) -> DiscoLikeClient:
    return DiscoLikeClient(
        api_key="dk_test_key",
        base_url=base_url,
        cache=cache,
        cost_tracker=cost_tracker,
        timeout=5.0,
    )


@pytest.fixture
def dry_client(
    base_url: str, cache: CacheManager, cost_tracker: CostTracker
) -> DiscoLikeClient:
    return DiscoLikeClient(
        api_key="dk_test_key",
        base_url=base_url,
        cache=cache,
        cost_tracker=cost_tracker,
        dry_run=True,
        timeout=5.0,
    )


class TestAccountStatus:
    @respx.mock
    def test_account_status_success(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("account_status.json")
        respx.get(f"{base_url}/usage").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        result = client.account_status()
        assert isinstance(result, AccountStatus)
        assert result.account_status == "active"
        assert result.plan == "starter"
        assert result.usage is not None
        assert result.usage.month_to_date_requests == 42
        assert result.usage.month_to_date_spend == Decimal("12.5")

    @respx.mock
    def test_account_status_updates_plan(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        fixture = _load_fixture("account_status.json")
        fixture["plan"] = "pro"
        respx.get(f"{base_url}/usage").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client.account_status()
        assert client.cost_tracker.plan == "pro"

    @respx.mock
    def test_account_status_cached(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        fixture = _load_fixture("account_status.json")
        route = respx.get(f"{base_url}/usage").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        # First call hits API
        client.account_status()
        assert route.call_count == 1
        # Second call should use cache
        result = client.account_status()
        assert route.call_count == 1
        assert result.plan == "starter"


class TestDiscover:
    @respx.mock
    def test_discover_success(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("discover_results.json")
        respx.get(f"{base_url}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        result = client.discover(filters={"domain": ["leadgrow.ai"]}, max_records=25)
        assert isinstance(result, DiscoverResult)
        assert result.count == 2
        assert len(result.records) == 2
        assert result.records[0].domain == "example-agency.com"
        assert result.records[1].similarity == 87

    @respx.mock
    def test_discover_tracks_cost(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("discover_results.json")
        respx.get(f"{base_url}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client.discover(filters={"domain": ["test.com"]})
        assert client.cost_tracker.session_total > Decimal("0")
        assert client.cost_tracker.last_call is not None
        assert client.cost_tracker.last_call.endpoint == "discover"
        assert client.cost_tracker.last_call.records_returned == 2


class TestExtract:
    @respx.mock
    def test_extract_success(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("extract_result.json")
        respx.get(f"{base_url}/extract").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        result = client.extract("example-agency.com")
        assert isinstance(result, ExtractResult)
        assert result.domain == "example-agency.com"
        assert "B2B lead generation" in (result.text or "")

    @respx.mock
    def test_extract_cached(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("extract_result.json")
        route = respx.get(f"{base_url}/extract").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client.extract("example-agency.com")
        assert route.call_count == 1
        result = client.extract("example-agency.com")
        assert route.call_count == 1
        assert result.domain == "example-agency.com"


class TestBusinessProfile:
    @respx.mock
    def test_profile_success(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("business_profile.json")
        respx.get(f"{base_url}/bizdata").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        result = client.business_profile("example-agency.com")
        assert isinstance(result, BusinessProfile)
        assert result.domain == "example-agency.com"
        assert result.score == 450
        assert result.address is not None
        assert result.address["city"] == "Austin"

    @respx.mock
    def test_profile_cached(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("business_profile.json")
        route = respx.get(f"{base_url}/bizdata").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client.business_profile("example-agency.com")
        result = client.business_profile("example-agency.com")
        assert route.call_count == 1
        assert result.name == "Example Agency"


class TestScore:
    @respx.mock
    def test_score_success(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("score_result.json")
        respx.get(f"{base_url}/score").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        result = client.score("example-agency.com")
        assert isinstance(result, ScoreResult)
        assert result.score == 450
        assert result.parameters is not None
        assert result.parameters.base_score == 400


class TestGrowth:
    @respx.mock
    def test_growth_success(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("growth_result.json")
        respx.get(f"{base_url}/growth").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        result = client.growth("example-agency.com")
        assert isinstance(result, GrowthResult)
        assert result.score_growth_3m == 0.12
        assert result.subdomain_growth_3m == 0.05


class TestSavedQueries:
    @respx.mock
    def test_saved_queries_success(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("saved_queries.json")
        respx.get(f"{base_url}/queries/saved").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        result = client.saved_queries()
        assert len(result) == 1
        assert isinstance(result[0], SavedQuery)
        assert result[0].query_id == "q_abc123"
        assert result[0].domain_count == 2


class TestErrorHandling:
    @respx.mock
    def test_401_raises_auth_error(self, client: DiscoLikeClient, base_url: str) -> None:
        respx.get(f"{base_url}/usage").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        with pytest.raises(AuthError, match="Invalid or expired API key"):
            client.account_status()

    @respx.mock
    def test_429_triggers_retry_then_succeeds(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        fixture = _load_fixture("account_status.json")
        route = respx.get(f"{base_url}/usage").mock(
            side_effect=[
                httpx.Response(429, headers={"retry-after": "0"}),
                httpx.Response(200, json=fixture),
            ]
        )
        result = client.account_status()
        assert route.call_count == 2
        assert result.plan == "starter"

    @respx.mock
    def test_429_exhausted_raises_rate_limit(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        respx.get(f"{base_url}/usage").mock(
            return_value=httpx.Response(429, headers={"retry-after": "0"})
        )
        with pytest.raises(RateLimitError, match="Rate limited"):
            client.account_status()

    @respx.mock
    def test_500_triggers_retry_then_succeeds(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        fixture = _load_fixture("account_status.json")
        route = respx.get(f"{base_url}/usage").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, json=fixture),
            ]
        )
        result = client.account_status()
        assert route.call_count == 2
        assert result.plan == "starter"

    @respx.mock
    def test_500_exhausted_raises_api_error(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        respx.get(f"{base_url}/usage").mock(
            return_value=httpx.Response(500)
        )
        with pytest.raises(APIError, match="Server error"):
            client.account_status()

    @respx.mock
    def test_400_raises_api_error(self, client: DiscoLikeClient, base_url: str) -> None:
        respx.get(f"{base_url}/extract").mock(
            return_value=httpx.Response(400, text="Bad request")
        )
        with pytest.raises(APIError, match="API error 400"):
            client.extract("bad.com")


class TestDryRun:
    def test_dry_run_discover_skips_http(self, dry_client: DiscoLikeClient) -> None:
        # No respx mock needed — no HTTP calls should be made
        result = dry_client.discover(
            filters={"domain": ["test.com"]}, max_records=50
        )
        assert isinstance(result, DiscoverResult)
        assert result.count == 0
        assert result.records == []
        # Cost should be estimated, not recorded
        assert dry_client.cost_tracker.session_total == Decimal("0")
        assert dry_client.cost_tracker.last_call is not None
        assert dry_client.cost_tracker.last_call.estimated is True

    def test_dry_run_extract_skips_http(self, dry_client: DiscoLikeClient) -> None:
        result = dry_client.extract("test.com")
        assert isinstance(result, ExtractResult)
        assert result.domain == "test.com"

    def test_dry_run_account_status_skips_http(
        self, dry_client: DiscoLikeClient
    ) -> None:
        result = dry_client.account_status()
        assert isinstance(result, AccountStatus)

    def test_dry_run_score_skips_http(self, dry_client: DiscoLikeClient) -> None:
        result = dry_client.score("test.com")
        assert isinstance(result, ScoreResult)
        assert result.domain == "test.com"


class TestCacheIntegration:
    @respx.mock
    def test_cache_hit_skips_http(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        """Pre-populate cache, verify no HTTP call is made."""
        fixture = _load_fixture("score_result.json")
        # Pre-populate cache
        assert client.cache is not None
        client.cache.set(
            "score:example-agency.com",
            json.dumps(fixture),
            "score",
        )
        # Mock should NOT be called
        route = respx.get(f"{base_url}/score").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        result = client.score("example-agency.com")
        assert route.call_count == 0
        assert result.score == 450

    @respx.mock
    def test_count_not_cached(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        """Count endpoint should never use cache."""
        respx.get(f"{base_url}/count").mock(
            return_value=httpx.Response(200, json={"count": 42})
        )
        result = client.count(filters={"domain": ["test.com"]})
        assert isinstance(result, CountResult)
        assert result.count == 42


class TestAsyncSubmit:
    @respx.mock
    def test_discogen_submit_posts_to_correct_endpoint(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        respx.post(f"{base_url}/discogen/process").mock(
            return_value=httpx.Response(200, json={"task_id": "t-abc", "status": "in_progress"})
        )
        result = client.discogen_submit({"domains": ["x.com"], "prompt": "test"})
        assert result["task_id"] == "t-abc"
        assert result["status"] == "in_progress"

    @respx.mock
    def test_validate_icp_submit_posts_to_correct_endpoint(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        respx.post(f"{base_url}/validate/icp").mock(
            return_value=httpx.Response(200, json={"task_id": "t-val", "status": "in_progress"})
        )
        result = client.validate_icp_submit({"domains": ["x.com"], "icp_text": "test"})
        assert result["task_id"] == "t-val"

    @respx.mock
    def test_segment_submit_posts_to_correct_endpoint(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        respx.post(f"{base_url}/segment").mock(
            return_value=httpx.Response(200, json={"task_id": "t-seg", "status": "in_progress"})
        )
        result = client.segment_submit({"domains": ["x.com"]})
        assert result["task_id"] == "t-seg"

    def test_discogen_submit_dry_run_skips_http(
        self, dry_client: DiscoLikeClient
    ) -> None:
        result = dry_client.discogen_submit({"domains": ["x.com"], "prompt": "test"})
        assert result["task_id"] == "dry-run-task-id"
        assert result["status"] == "in_progress"

    def test_validate_icp_submit_dry_run_skips_http(
        self, dry_client: DiscoLikeClient
    ) -> None:
        result = dry_client.validate_icp_submit({"domains": ["x.com"], "icp_text": "test"})
        assert result["task_id"] == "dry-run-task-id"
        assert result["status"] == "in_progress"

    def test_segment_submit_dry_run_skips_http(
        self, dry_client: DiscoLikeClient
    ) -> None:
        result = dry_client.segment_submit({"domains": ["x.com"]})
        assert result["task_id"] == "dry-run-task-id"
        assert result["status"] == "in_progress"


class TestTaskStatus:
    @respx.mock
    def test_task_status_gets_shared_endpoint(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        """All async task types share /discogen/status/ for polling."""
        respx.get(f"{base_url}/discogen/status/task-123").mock(
            return_value=httpx.Response(200, json={"task_id": "task-123", "status": "completed"})
        )
        result = client.task_status("task-123")
        assert result["task_id"] == "task-123"
        assert result["status"] == "completed"

    @respx.mock
    def test_task_status_in_progress(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        respx.get(f"{base_url}/discogen/status/task-456").mock(
            return_value=httpx.Response(200, json={"status": "in_progress", "progress": 40})
        )
        result = client.task_status("task-456")
        assert result["status"] == "in_progress"
        assert result["progress"] == 40

    @respx.mock
    def test_task_status_still_makes_http_in_dry_run(
        self, dry_client: DiscoLikeClient, base_url: str
    ) -> None:
        """task_status needs real task_ids — should still hit HTTP even in dry_run."""
        route = respx.get(f"{base_url}/discogen/status/task-real").mock(
            return_value=httpx.Response(200, json={"status": "completed"})
        )
        result = dry_client.task_status("task-real")
        assert route.call_count == 1
        assert result["status"] == "completed"


class TestTaskCancel:
    @respx.mock
    def test_task_cancel_sends_delete(
        self, client: DiscoLikeClient, base_url: str
    ) -> None:
        respx.delete(f"{base_url}/discogen/cancel/task-123").mock(
            return_value=httpx.Response(200, json={"cancelled": True, "task_id": "task-123"})
        )
        result = client.task_cancel("task-123")
        assert result["cancelled"] is True
        assert result["task_id"] == "task-123"

    @respx.mock
    def test_task_cancel_still_makes_http_in_dry_run(
        self, dry_client: DiscoLikeClient, base_url: str
    ) -> None:
        """task_cancel needs real task_ids — should still hit HTTP even in dry_run."""
        route = respx.delete(f"{base_url}/discogen/cancel/task-real").mock(
            return_value=httpx.Response(200, json={"cancelled": True})
        )
        result = dry_client.task_cancel("task-real")
        assert route.call_count == 1
        assert result["cancelled"] is True


class TestUsage:
    @respx.mock
    def test_usage_returns_stats(self, client: DiscoLikeClient, base_url: str) -> None:
        fixture = _load_fixture("account_status.json")
        respx.get(f"{base_url}/usage").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        usage = client.usage()
        assert usage.month_to_date_requests == 42
        assert usage.month_to_date_records == 350
