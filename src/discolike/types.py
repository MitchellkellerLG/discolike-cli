"""Pydantic v2 models for all DiscoLike API response shapes."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

# --- Account & Usage ---


class UsageStats(BaseModel):
    """Monthly usage statistics from account-status endpoint."""

    month_to_date_requests: int | None = None
    month_to_date_records: int | None = None
    month_to_date_spend: Decimal | None = None
    max_spend: Decimal | None = None
    total_available_spend: Decimal | None = None
    carryover_credits: Decimal | None = None
    top_up_credits: Decimal | None = None
    usage_summary: dict[str, int] | None = None


class AccountStatus(BaseModel):
    """Full account status response."""

    account_status: str | None = None
    plan: str | None = None
    usage: UsageStats | None = None


# --- Extract ---


class ExtractResult(BaseModel):
    """Result from the extract endpoint."""

    domain: str
    text: str | None = None


# --- Count ---


class CountResult(BaseModel):
    """Result from the count endpoint."""

    count: int


# --- Discover ---


class DiscoverRecord(BaseModel):
    """Single company record from discover results."""

    model_config = ConfigDict(extra="allow")

    domain: str
    name: str | None = None
    status: dict[str, Any] | str | None = None
    score: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    address: dict[str, Any] | None = None
    phones: list[str] | None = None
    public_emails: list[str] | None = None
    domain_associations: list[str] | None = None
    social_urls: list[str] | dict[str, str | None] | None = None
    redirect_domain: str | None = None
    description: str | None = None
    keywords: dict[str, float] | list[str] | None = None
    industry_groups: dict[str, float] | list[str] | None = None
    update_date: str | None = None
    similarity: float | None = None
    employees: str | None = None
    vendors: list[str] | None = None


class DiscoverResult(BaseModel):
    """Full discover response with records and count."""

    records: list[DiscoverRecord] = []
    count: int = 0


# --- Profile ---


class BusinessProfile(BaseModel):
    """Single company profile (same as DiscoverRecord minus employees, similarity, vendors)."""

    model_config = ConfigDict(extra="allow")

    domain: str
    name: str | None = None
    status: dict[str, Any] | str | None = None
    score: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    address: dict[str, Any] | None = None
    phones: list[str] | None = None
    public_emails: list[str] | None = None
    domain_associations: list[str] | None = None
    social_urls: list[str] | dict[str, str | None] | None = None
    redirect_domain: str | None = None
    description: str | None = None
    keywords: dict[str, float] | list[str] | None = None
    industry_groups: dict[str, float] | list[str] | None = None
    update_date: str | None = None


# --- Score ---


class ScoreParameters(BaseModel):
    """Scoring breakdown parameters."""

    base_score: float | None = None
    recency_multiplier: float | None = None
    growth_boost: float | None = None
    lookback_360: float | None = None
    lookback_720: float | None = None
    expiration_penalty: float | None = None


class ScoreResult(BaseModel):
    """Result from the score endpoint."""

    domain: str
    score: int | None = None
    parameters: ScoreParameters | None = None
    first_event: str | None = None


# --- Growth ---


class GrowthResult(BaseModel):
    """Result from the growth endpoint. Has dynamic quarterly fields."""

    model_config = ConfigDict(extra="allow")

    domain: str
    score_growth_3m: float | None = None
    subdomain_growth_3m: float | None = None


# --- Saved Queries ---


class SavedQuery(BaseModel):
    """A saved query from the API."""

    query_id: str | None = None
    query_name: str | None = None
    action: str | None = None
    user_name: str | None = None
    mtime: str | None = None
    domains: list[str] | None = None
    domain_count: int | None = None
    query_params: dict[str, Any] | None = None


# --- Cost Tracking ---


class CostBreakdown(BaseModel):
    """Cost breakdown for a single API call."""

    endpoint: str
    query_fee: Decimal = Decimal("0")
    record_fee: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    records_returned: int = 0
    session_total: Decimal = Decimal("0")
    budget_remaining: Decimal | None = None
    plan: str = ""
    estimated: bool = False


class CostMeta(BaseModel):
    """Cost metadata attached to every API response."""

    cost: CostBreakdown
    cached: bool = False
    timestamp: str = ""
