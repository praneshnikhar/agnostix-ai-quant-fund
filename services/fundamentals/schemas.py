"""Fundamental domain schemas (M2).

Strongly-typed internal contracts for company fundamentals. All financial
records preserve full provenance (.clinerules §5, §11):

- event/period time : the provider's original period or event timestamp
- received_at       : when our system received the record
- stored_at         : when persisted (set by storage layer)

Period semantics (§8): fiscal periods are NEVER conflated with calendar
dates. Every metric carries an explicit PeriodType + fiscal identifiers.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _require_tzaware(name: str, value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


class ProviderInfo(BaseModel):
    """Which provider/feed produced a record."""

    provider: str  # e.g. "fixture", "alpaca_fundamentals"
    raw_record_id: str | None = None


class DataQuality(StrEnum):
    OK = "ok"
    CONFLICTING = "conflicting"   # sources disagree; values preserved as-is
    INCOMPLETE = "incomplete"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


class PeriodType(StrEnum):
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    TTM = "ttm"


class StatementType(StrEnum):
    INCOME = "income"
    BALANCE = "balance"
    CASHFLOW = "cashflow"


class DocumentType(StrEnum):
    FILING = "filing"
    EARNINGS_RELEASE = "earnings_release"
    TRANSCRIPT = "transcript"
    IR_PRESENTATION = "ir_presentation"
    ANNOUNCEMENT = "announcement"
    NEWS = "news"


class CompanyProfile(BaseModel):
    symbol: str
    name: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    employees: int | None = Field(default=None, ge=0)
    currency: str = "USD"
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


class FinancialPeriod(BaseModel):
    """Explicit period identity — fiscal vs calendar never mixed."""

    period_type: PeriodType
    period_end: date
    fiscal_year: int | None = None
    fiscal_quarter: int | None = Field(default=None, ge=1, le=4)
    calendar_quarter: str | None = None  # e.g. "2026Q2" — informational only

    @model_validator(mode="after")
    def _quarter_consistency(self) -> FinancialPeriod:
        if self.period_type == PeriodType.QUARTERLY and self.fiscal_quarter is None:
            raise ValueError("quarterly periods must carry fiscal_quarter")
        if self.period_type == PeriodType.ANNUAL and self.fiscal_year is None:
            raise ValueError("annual periods must carry fiscal_year")
        return self


class FinancialMetric(BaseModel):
    """One reported financial figure with full provenance.

    `value` may be None when a provider reports the field as unavailable —
    unavailability is data, not an error to be papered over.
    """

    symbol: str
    metric: str                       # e.g. "revenue", "net_income", "eps_diluted"
    value: float | None = None
    period: FinancialPeriod
    currency: str = "USD"
    units: str = "usd"                # usd | usd_thousands | shares | ratio | percent
    quality: DataQuality = DataQuality.OK
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


class FinancialStatement(BaseModel):
    """A normalized statement: typed line items + raw payload preserved."""

    symbol: str
    statement_type: StatementType
    period: FinancialPeriod
    line_items: dict[str, float | None] = Field(default_factory=dict)
    currency: str = "USD"
    units: str = "usd"
    quality: DataQuality = DataQuality.OK
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


class IncomeStatement(FinancialStatement):
    statement_type: StatementType = StatementType.INCOME


class BalanceSheet(FinancialStatement):
    statement_type: StatementType = StatementType.BALANCE


class CashFlowStatement(FinancialStatement):
    statement_type: StatementType = StatementType.CASHFLOW


class EarningsEvent(BaseModel):
    """One earnings report event. Surprises are computed deterministically
    by the metrics layer when actual+estimate are both present — never by
    an LLM."""

    symbol: str
    event_time: datetime              # when results were published
    reporting_period: FinancialPeriod
    eps_actual: float | None = None
    eps_estimate: float | None = None
    revenue_actual: float | None = None
    revenue_estimate: float | None = None
    currency: str = "USD"
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


class EarningsResult(BaseModel):
    """Earnings event + deterministically derived surprise fields."""

    event: EarningsEvent
    eps_surprise: float | None = None          # actual - estimate
    eps_surprise_pct: float | None = None      # surprise / |estimate|
    revenue_surprise: float | None = None
    revenue_surprise_pct: float | None = None


class ValuationSnapshot(BaseModel):
    """Point-in-time valuation context. Fields absent from the provider
    stay None — never imputed."""

    symbol: str
    as_of: datetime
    price: float | None = Field(default=None, gt=0)
    market_cap: float | None = Field(default=None, gt=0)
    pe_ratio: float | None = None
    forward_pe: float | None = None
    ps_ratio: float | None = None
    ev_ebitda: float | None = None
    fcf_yield: float | None = None
    shares_outstanding: float | None = Field(default=None, gt=0)
    currency: str = "USD"
    provider_info: ProviderInfo
    received_at: datetime
    stored_at: datetime | None = None

    @field_validator("as_of", "received_at", "stored_at")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        return _require_tzaware("timestamp", v) if v is not None else None

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class FundamentalDataStatus(BaseModel):
    """Availability report for one fundamental datatype of one symbol."""

    datatype: str  # profile | metrics | statements | earnings | valuation | documents
    symbol: str
    state: DataQuality
    detail: str | None = None


class ResearchDocument(BaseModel):
    """Normalized research document (filings, releases, transcripts, news)."""

    document_id: str                  # stable id within provider namespace
    symbol: str
    title: str = Field(min_length=1)
    document_type: DocumentType
    source: str | None = None
    url: str | None = None
    published_at: datetime
    retrieved_at: datetime
    content: str | None = None        # normalized text; None => metadata only
    summary: str | None = None
    provider_info: ProviderInfo
    stored_at: datetime | None = None

    @field_validator("published_at", "retrieved_at", "stored_at")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        return _require_tzaware("timestamp", v) if v is not None else None

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class DerivedMetric(BaseModel):
    """Reproducible derived metric: formula + inputs + provenance (§7)."""

    symbol: str
    metric: str
    value: float
    formula: str                      # e.g. "(revenue_t - revenue_{t-4}) / revenue_{t-4}"
    inputs: list[dict[str, Any]]      # each: {metric, period_end, value, source}
    calculated_at: datetime
    currency: str = "USD"

    @field_validator("calculated_at")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        return _require_tzaware("calculated_at", v)


__all__ = [
    "BalanceSheet",
    "CashFlowStatement",
    "CompanyProfile",
    "DataQuality",
    "DerivedMetric",
    "DocumentType",
    "EarningsEvent",
    "EarningsResult",
    "FinancialMetric",
    "FinancialPeriod",
    "FinancialStatement",
    "FundamentalDataStatus",
    "IncomeStatement",
    "PeriodType",
    "ProviderInfo",
    "ResearchDocument",
    "StatementType",
    "ValuationSnapshot",
]