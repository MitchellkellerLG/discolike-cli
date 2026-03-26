"""Cost tracking for DiscoLike CLI -- per-call and session totals."""

from __future__ import annotations

from decimal import Decimal

from rich.console import Console

from discolike.cache import CacheManager
from discolike.constants import PLAN_PRICING
from discolike.errors import BudgetExceededError
from discolike.types import CostBreakdown

stderr_console = Console(stderr=True)


class CostTracker:
    """Tracks API costs per-call and across the session."""

    def __init__(
        self, plan: str = "starter", cache: CacheManager | None = None
    ) -> None:
        self._plan = plan.lower()
        self._cache = cache
        self._session_calls: list[CostBreakdown] = []
        self._session_total = Decimal("0")
        self._budget_limit: Decimal | None = None
        self._last_call: CostBreakdown | None = None

    @property
    def plan(self) -> str:
        return self._plan

    @property
    def last_call(self) -> CostBreakdown | None:
        return self._last_call

    @property
    def session_total(self) -> Decimal:
        return self._session_total

    @property
    def session_calls(self) -> list[CostBreakdown]:
        return self._session_calls

    def set_plan(self, plan: str, budget_limit: Decimal | None = None) -> None:
        """Update plan after account-status call."""
        self._plan = plan.lower()
        self._budget_limit = budget_limit

    def record_call(self, endpoint: str, records_returned: int) -> CostBreakdown:
        """Record an actual API call cost. Returns breakdown."""
        pricing = PLAN_PRICING.get(self._plan, PLAN_PRICING["starter"])
        query_fee = pricing.per_query
        record_fee = Decimal(records_returned) / 1000 * pricing.per_1k_records
        total = query_fee + record_fee
        self._session_total += total

        breakdown = CostBreakdown(
            endpoint=endpoint,
            query_fee=query_fee,
            record_fee=record_fee,
            total=total,
            records_returned=records_returned,
            session_total=self._session_total,
            budget_remaining=(
                self._budget_limit - self._session_total if self._budget_limit else None
            ),
            plan=self._plan,
            estimated=False,
        )
        self._session_calls.append(breakdown)
        self._last_call = breakdown

        # Persist to SQLite if cache available
        if self._cache:
            self._cache.record_cost(
                endpoint=endpoint,
                query_fee=str(query_fee),
                record_fee=str(record_fee),
                total=str(total),
                records_returned=records_returned,
                plan=self._plan,
            )

        self._check_budget()
        return breakdown

    def estimate(self, endpoint: str, estimated_records: int) -> CostBreakdown:
        """Dry-run estimate. Does NOT accumulate to session."""
        pricing = PLAN_PRICING.get(self._plan, PLAN_PRICING["starter"])
        query_fee = pricing.per_query
        record_fee = Decimal(estimated_records) / 1000 * pricing.per_1k_records
        total = query_fee + record_fee
        breakdown = CostBreakdown(
            endpoint=endpoint,
            query_fee=query_fee,
            record_fee=record_fee,
            total=total,
            records_returned=estimated_records,
            session_total=self._session_total,
            budget_remaining=(
                self._budget_limit - self._session_total if self._budget_limit else None
            ),
            plan=self._plan,
            estimated=True,
        )
        self._last_call = breakdown
        return breakdown

    def _check_budget(self) -> None:
        """Warn at 80%/95%, raise at 100%."""
        if self._budget_limit is None or self._budget_limit == 0:
            return
        pct = (self._session_total / self._budget_limit) * 100
        if pct >= 100:
            raise BudgetExceededError(
                f"Budget exhausted: ${self._session_total:.2f} spent "
                f"of ${self._budget_limit:.2f} limit."
            )
        if pct >= 95:
            stderr_console.print(
                f"[bold red]WARNING: {pct:.0f}% of budget consumed "
                f"(${self._session_total:.2f} / ${self._budget_limit:.2f})[/]"
            )
        elif pct >= 80:
            stderr_console.print(
                f"[yellow]WARNING: {pct:.0f}% of budget consumed "
                f"(${self._session_total:.2f} / ${self._budget_limit:.2f})[/]"
            )
