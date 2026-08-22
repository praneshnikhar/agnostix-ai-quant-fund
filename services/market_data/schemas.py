"""Internal market-data contracts (M1).

Strongly-typed domain models that all future AI agents consume.
Agents must NEVER depend on provider-specific response objects —
only on these schemas.

Provenance rules (.clinerules §11):
- event_time  : the provider's original event/publication timestamp
                (NEVER silently replaced or fabricated)
- received_at : when our system received the record from the provider
- stored_at   : when the record was persisted (set by storage layer)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator

CLOCK_SKEW_TOLERANCE_SECONDS = 300  # 5 minutes


def _require_tzaware(name: str, value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


class FreshnessState(StrEnum):
    """Explicit data-quality states. A stale record must never appear fresh."""

    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"
    INVALID = "invalid"


# Worst-first ordering used to compute overall snapshot state.
_FRESHNESS_SEVERITY: dict[FreshnessState, int] = {
    FreshnessState.MISSING: 3,
    FreshnessState.INVALID: 2,
    FreshnessState.STALE: 1,
    FreshnessState.FRESH: 0,
}


class ProviderInfo(BaseModel):
    """Which provider/feed produced a record."""

    provider: str  # e.g. "alpaca_market_data"
    feed: str | None = None  # e.g. "iex", "sip"
    raw_record_id: str | None = None


class Bar(BaseModel):
    symbol: str
    event_time: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    trade_count: int | None = None
    vwap: float | None = None
    provider_info: ProviderInfo
    received_at: datetime
    stored_at: datetime | None = None

    @field_validator("event_time", "received_at", "stored_at")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        return _require_tzaware("timestamp", v) if v is not None else None

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class Quote(BaseModel):
    symbol: str
    event_time: datetime
    bid_price: float | None = None
    bid_size: float | None = None
    ask_price: float | None = None
    ask_size: float | None = None
    last_price: float | None = None
    provider_info: ProviderInfo
    received_at: datetime
    stored_at: datetime | None = None

    @field_validator("event_time", "received_at", "stored_at")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        return _require_tzaware("timestamp", v) if v is not None else None

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class Trade(BaseModel):
    symbol: str
    event_time: datetime
    price: float = Field(gt=0)
    size: float = Field(gt=0)
    conditions: list[str] = Field(default_factory=list)
    provider_trade_id: str | None = None
    provider_info: ProviderInfo
    received_at: datetime
    stored_at: datetime | None = None

    @field_validator("event_time", "received_at", "stored_at")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        return _require_tzaware("timestamp", v) if v is not None else None

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class NewsArticle(BaseModel):
    provider_article_id: str
    headline: str = Field(min_length=1)
    summary: str | None = None
    source: str | None = None
    url: str | None = None
    symbols: list[str] = Field(default_factory=list)
    published_at: datetime
    provider_info: ProviderInfo
    received_at: datetime
    stored_at: datetime | None = None

    @field_validator("published_at", "received_at", "stored_at")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        return _require_tzaware("timestamp", v) if v is not None else None

    @field_validator("symbols")
    @classmethod
    def _upper_symbols(cls, v: list[str]) -> list[str]:
        return [s.upper() for s in v]


class Security(BaseModel):
    symbol: str
    name: str | None = None
    exchange: str | None = None
    asset_class: str = "us_equity"
    status: str = "active"  # active | inactive
    provider_info: ProviderInfo
    received_at: datetime
    stored_at: datetime | None = None

    @field_validator("received_at", "stored_at")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        return _require_tzaware("timestamp", v) if v is not None else None

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class MarketDataStatus(BaseModel):
    """Freshness report for one datatype of one symbol."""

    datatype: str  # bars | quotes | trades | news | security_metadata
    symbol: str
    state: FreshnessState
    as_of: datetime | None = None  # newest event_time, None when missing
    age_seconds: float | None = None
    threshold_seconds: float | None = None
    detail: str | None = None


class MarketSnapshot(BaseModel):
    """Point-in-time research view for one symbol.

    fundamentals/macro are structurally present but explicitly NOT populated
    in M1 (no fabrication). Later milestones fill them in.
    """

    FUNDAMENTALS_UNAVAILABLE_IN_M1: ClassVar[str] = "unavailable_in_m1"

    symbol: str
    generated_at: datetime
    market: dict[str, Any] = Field(default_factory=dict)
    news: list[NewsArticle] = Field(default_factory=list)
    fundamentals: dict[str, Any] = Field(
        default_factory=lambda: {"status": MarketSnapshot.FUNDAMENTALS_UNAVAILABLE_IN_M1}
    )
    macro: dict[str, Any] = Field(
        default_factory=lambda: {"status": MarketSnapshot.FUNDAMENTALS_UNAVAILABLE_IN_M1}
    )
    data_quality: list[MarketDataStatus] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        return _require_tzaware("generated_at", v)

    @property
    def overall_state(self) -> FreshnessState:
        """Worst data-quality state across all reported datatypes."""
        worst = FreshnessState.FRESH
        for status in self.data_quality:
            if _FRESHNESS_SEVERITY[status.state] > _FRESHNESS_SEVERITY[worst]:
                worst = status.state
        return worst


__all__ = [
    "Bar",
    "FreshnessState",
    "MarketDataStatus",
    "MarketSnapshot",
    "NewsArticle",
    "ProviderInfo",
    "Quote",
    "Security",
    "Trade",
]
