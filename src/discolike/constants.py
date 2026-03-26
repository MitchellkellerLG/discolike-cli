"""Constants for DiscoLike CLI — pricing, categories, enums."""

from decimal import Decimal
from typing import NamedTuple

API_BASE_URL = "https://api.discolike.com/v1"
AUTH_HEADER = "x-discolike-key"
CONFIG_DIR = "~/.discolike"
CONFIG_FILE = "config.yaml"
CACHE_DB = "cache.db"

# Cache TTLs in seconds
CACHE_TTL_ACCOUNT_STATUS = 3600        # 1 hour
CACHE_TTL_EXTRACT = 7_776_000          # 90 days
CACHE_TTL_PROFILE = 604_800            # 7 days
CACHE_TTL_SCORE = 604_800              # 7 days


class PlanPricing(NamedTuple):
    name: str
    monthly_price: Decimal
    per_query: Decimal
    per_1k_records: Decimal
    max_exclusion_records: int


PLAN_PRICING: dict[str, PlanPricing] = {
    "starter": PlanPricing("Starter", Decimal("99"), Decimal("0.18"), Decimal("3.50"), 0),
    "pro": PlanPricing("Pro", Decimal("199"), Decimal("0.15"), Decimal("3.00"), 25_000),
    "team": PlanPricing("Team", Decimal("399"), Decimal("0.12"), Decimal("2.50"), 50_000),
    "company": PlanPricing("Company", Decimal("799"), Decimal("0.10"), Decimal("2.00"), 100_000),
    "enterprise": PlanPricing(
        "Enterprise", Decimal("1599"), Decimal("0.08"), Decimal("1.50"), 200_000,
    ),
}

# Plan hierarchy for gate checks (index = level)
PLAN_LEVELS = ["starter", "pro", "team", "company", "enterprise"]

# Features requiring minimum plan level
PLAN_GATED_FEATURES: dict[str, str] = {
    "contacts": "team",
    "match": "team",
    "vendors": "team",
    "subsidiaries": "enterprise",
}

CATEGORIES = [
    "ACCOUNTING", "ADVERTISING_AND_MARKETING", "AGRICULTURE_AND_NATURAL_RESOURCES",
    "AUTOMOTIVE", "BIG_DATA_AND_ANALYTICS", "BIOTECHNOLOGY",
    "BLOCKCHAIN_AND_CRYPTOCURRENCY", "BUSINESS_PRODUCTS_AND_SERVICES",
    "CLOUD_COMPUTING", "COMPUTER_HARDWARE_AND_SEMICONDUCTORS", "CONSTRUCTION",
    "CONSUMER_PRODUCTS", "CONSUMER_SERVICES", "CYBERSECURITY",
    "DEFENSE_AND_AEROSPACE", "E-COMMERCE", "EDUCATION", "ENERGY", "ENGINEERING",
    "ENTERTAINMENT", "ENVIRONMENTAL_SERVICES", "FASHION_TEXTILE_AND_APPAREL",
    "FINANCIAL_SERVICES", "FOOD_AND_BEVERAGE", "GAMING_AND_ESPORTS",
    "GOVERNMENT_SERVICES", "HEALTHCARE", "HOSPITALITY", "HUMAN_RESOURCES",
    "INSURANCE", "IT_SERVICES", "LEGAL", "MANUFACTURING", "MEDIA",
    "MINING_AND_METALS", "NONPROFIT_AND_PHILANTHROPY", "OIL_AND_GAS",
    "PHARMACEUTICALS", "PRIVATE_EQUITY_AND_VENTURE_CAPITAL", "REAL_ESTATE",
    "RENEWABLE_ENERGY", "RESTAURANTS", "RETAIL", "SAAS", "SECURITY", "SOFTWARE",
    "SPORTS_AND_RECREATION", "SUPPLY_CHAIN_AND_PROCUREMENT",
    "TELECOMMUNICATIONS", "TRAVEL", "WELLNESS_AND_LIFESTYLE",
]

EMPLOYEE_RANGES = [
    "1-10", "11-50", "51-200", "201-500", "501-1000",
    "1001-5000", "5001-10000", "10001+",
]

VARIANCE_CHOICES = ["LOW", "MEDIUM", "HIGH", "UNRESTRICTED"]

# Default fields for discover output
DEFAULT_DISCOVER_FIELDS = [
    "domain", "name", "similarity", "score", "employees", "description",
]

# Standard CSV export columns
CSV_EXPORT_COLUMNS = [
    "domain", "name", "score", "similarity", "employees",
    "city", "state", "country", "public_emails", "social_urls", "description",
]
