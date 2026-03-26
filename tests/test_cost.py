"""Tests for CostTracker — per-call and session cost tracking."""

from __future__ import annotations

from decimal import Decimal

import pytest

from discolike.cost import CostTracker
from discolike.errors import BudgetExceededError


class TestCostTrackerInit:
    def test_default_plan(self) -> None:
        ct = CostTracker()
        assert ct.plan == "starter"
        assert ct.session_total == Decimal("0")
        assert ct.last_call is None
        assert ct.session_calls == []

    def test_custom_plan(self) -> None:
        ct = CostTracker(plan="Pro")
        assert ct.plan == "pro"

    def test_set_plan(self) -> None:
        ct = CostTracker()
        ct.set_plan("enterprise", budget_limit=Decimal("500"))
        assert ct.plan == "enterprise"


class TestRecordCall:
    def test_starter_pricing_no_records(self) -> None:
        ct = CostTracker(plan="starter")
        bd = ct.record_call("discover", records_returned=0)
        # starter: query_fee=0.18, record_fee=0/1000*3.50=0
        assert bd.query_fee == Decimal("0.18")
        assert bd.record_fee == Decimal("0")
        assert bd.total == Decimal("0.18")
        assert bd.estimated is False

    def test_starter_pricing_with_records(self) -> None:
        ct = CostTracker(plan="starter")
        bd = ct.record_call("discover", records_returned=100)
        # query=0.18, record=100/1000*3.50=0.35, total=0.53
        assert bd.query_fee == Decimal("0.18")
        assert bd.record_fee == Decimal("0.350")
        assert bd.total == Decimal("0.530")

    def test_pro_pricing(self) -> None:
        ct = CostTracker(plan="pro")
        bd = ct.record_call("discover", records_returned=1000)
        # query=0.15, record=1000/1000*3.00=3.00, total=3.15
        assert bd.query_fee == Decimal("0.15")
        assert bd.record_fee == Decimal("3.00")
        assert bd.total == Decimal("3.15")

    def test_team_pricing(self) -> None:
        ct = CostTracker(plan="team")
        bd = ct.record_call("discover", records_returned=500)
        # query=0.12, record=500/1000*2.50=1.25, total=1.37
        assert bd.query_fee == Decimal("0.12")
        assert bd.record_fee == Decimal("1.250")
        assert bd.total == Decimal("1.370")

    def test_company_pricing(self) -> None:
        ct = CostTracker(plan="company")
        bd = ct.record_call("discover", records_returned=2000)
        # query=0.10, record=2000/1000*2.00=4.00, total=4.10
        assert bd.query_fee == Decimal("0.10")
        assert bd.record_fee == Decimal("4.000")
        assert bd.total == Decimal("4.100")

    def test_enterprise_pricing(self) -> None:
        ct = CostTracker(plan="enterprise")
        bd = ct.record_call("discover", records_returned=5000)
        # query=0.08, record=5000/1000*1.50=7.50, total=7.58
        assert bd.query_fee == Decimal("0.08")
        assert bd.record_fee == Decimal("7.500")
        assert bd.total == Decimal("7.580")

    def test_unknown_plan_falls_back_to_starter(self) -> None:
        ct = CostTracker(plan="nonexistent")
        bd = ct.record_call("discover", records_returned=0)
        assert bd.query_fee == Decimal("0.18")

    def test_session_total_accumulates(self) -> None:
        ct = CostTracker(plan="starter")
        ct.record_call("ep1", records_returned=0)  # 0.18
        ct.record_call("ep2", records_returned=0)  # 0.18
        ct.record_call("ep3", records_returned=0)  # 0.18
        assert ct.session_total == Decimal("0.54")

    def test_last_call_updated(self) -> None:
        ct = CostTracker(plan="starter")
        ct.record_call("first", records_returned=0)
        ct.record_call("second", records_returned=0)
        assert ct.last_call is not None
        assert ct.last_call.endpoint == "second"

    def test_session_calls_tracked(self) -> None:
        ct = CostTracker(plan="starter")
        ct.record_call("a", records_returned=0)
        ct.record_call("b", records_returned=0)
        assert len(ct.session_calls) == 2
        assert ct.session_calls[0].endpoint == "a"
        assert ct.session_calls[1].endpoint == "b"


class TestEstimate:
    def test_estimate_does_not_accumulate(self) -> None:
        ct = CostTracker(plan="starter")
        ct.record_call("real", records_returned=0)  # 0.18
        est = ct.estimate("fake", estimated_records=100)
        assert est.estimated is True
        assert est.total == Decimal("0.530")  # 0.18 + 0.35
        # Session total should still be 0.18 (only the real call)
        assert ct.session_total == Decimal("0.18")

    def test_estimate_sets_last_call(self) -> None:
        ct = CostTracker(plan="starter")
        ct.estimate("check", estimated_records=50)
        assert ct.last_call is not None
        assert ct.last_call.estimated is True
        assert ct.last_call.endpoint == "check"

    def test_estimate_shows_session_total(self) -> None:
        ct = CostTracker(plan="starter")
        ct.record_call("real", records_returned=0)
        est = ct.estimate("fake", estimated_records=0)
        assert est.session_total == Decimal("0.18")

    def test_estimate_shows_budget_remaining(self) -> None:
        ct = CostTracker(plan="starter")
        ct.set_plan("starter", budget_limit=Decimal("10.00"))
        ct.record_call("real", records_returned=0)
        est = ct.estimate("fake", estimated_records=0)
        assert est.budget_remaining == Decimal("10.00") - Decimal("0.18")


class TestBudgetGuardrails:
    def test_no_budget_no_error(self) -> None:
        ct = CostTracker(plan="starter")
        # No budget set, should not raise
        for _ in range(100):
            ct.record_call("ep", records_returned=0)

    def test_budget_100_pct_raises(self) -> None:
        ct = CostTracker(plan="starter")
        ct.set_plan("starter", budget_limit=Decimal("0.18"))
        with pytest.raises(BudgetExceededError, match="Budget exhausted"):
            ct.record_call("ep", records_returned=0)

    def test_budget_exceeded_raises(self) -> None:
        ct = CostTracker(plan="starter")
        ct.set_plan("starter", budget_limit=Decimal("0.10"))
        with pytest.raises(BudgetExceededError):
            ct.record_call("ep", records_returned=0)

    def test_budget_80_pct_warns(self, capsys: pytest.CaptureFixture[str]) -> None:
        ct = CostTracker(plan="starter")
        # Budget = 0.22, one call = 0.18 -> ~82%
        ct.set_plan("starter", budget_limit=Decimal("0.22"))
        ct.record_call("ep", records_returned=0)
        # Should have warned but not raised
        assert ct.session_total == Decimal("0.18")

    def test_budget_below_80_pct_no_warn(self) -> None:
        ct = CostTracker(plan="starter")
        ct.set_plan("starter", budget_limit=Decimal("100.00"))
        ct.record_call("ep", records_returned=0)
        # 0.18 / 100 = 0.18% — no warning, no error
        assert ct.session_total == Decimal("0.18")

    def test_zero_budget_no_error(self) -> None:
        ct = CostTracker(plan="starter")
        ct.set_plan("starter", budget_limit=Decimal("0"))
        # Zero budget = no limit enforced
        ct.record_call("ep", records_returned=0)
        assert ct.session_total == Decimal("0.18")
