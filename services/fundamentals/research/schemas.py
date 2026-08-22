"""Research output contracts (M2, .clinerules §13–§20).

Strictly structured thesis schema with constrained vocabularies,
fact/interpretation/conclusion separation, evidence references, and the
critic verdict schema. The proposing agent and critic are functionally
separate; the critic never silently rewrites a thesis.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FundamentalView(StrEnum):
    """Constrained vocabulary (§14). No arbitrary labels."""

    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ClaimKind(StrEnum):
    FACT = "FACT"
    INTERPRETATION = "INTERPRETATION"
    CONCLUSION = "CONCLUSION"


class EvidenceRef(BaseModel):
    """Reference to supporting evidence (§16)."""

    evidence_id: str
    source: str  # provider/document id — never invented
    source_type: str  # metric | document | earnings | valuation | news
    relevant_period: str | None = None
    claim_supported: str
    url: str | None = None  # only URLs present in context
    data_reference: dict[str, Any] | None = None


class ResearchStatement(BaseModel):
    """One fact / interpretation / conclusion statement (§18)."""

    kind: ClaimKind
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class Assessment(BaseModel):
    """One assessment dimension of the thesis."""

    area: str  # growth | profitability | cash_flow | balance_sheet | valuation
    summary: str
    statements: list[ResearchStatement] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class Catalyst(BaseModel):
    description: str
    expected_timeframe: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    description: str
    severity: str = "medium"  # low | medium | high
    evidence_ids: list[str] = Field(default_factory=list)


class InvalidationCondition(BaseModel):
    condition: str
    observable_signal: str


class DataQualityNote(BaseModel):
    area: str
    quality: str  # ok | conflicting | incomplete | invalid | unavailable
    detail: str | None = None


class InvestmentThesis(BaseModel):
    """Canonical structured research output (§13)."""

    symbol: str
    research_timestamp: datetime
    fundamental_view: FundamentalView
    # Confidence in the QUALITY/STRENGTH of the research conclusion —
    # NOT a probability of future stock return (§15).
    confidence: float = Field(ge=0.0, le=1.0)
    investment_thesis: str = Field(min_length=1)

    financial_assessment: Assessment
    growth_assessment: Assessment
    profitability_assessment: Assessment
    cash_flow_assessment: Assessment
    balance_sheet_assessment: Assessment
    valuation_assessment: Assessment

    catalysts: list[Catalyst] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    bear_case: str = ""
    invalidation_conditions: list[InvalidationCondition] = Field(default_factory=list)

    evidence: list[EvidenceRef] = Field(default_factory=list)
    data_quality: list[DataQualityNote] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


# ---------------------------------------------------------------------------
# Critic contracts (§19/§20)
# ---------------------------------------------------------------------------


class Verdict(StrEnum):
    PASS = "PASS"
    REVISE = "REVISE"
    REJECT = "REJECT"


class ClaimCheckStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"


class ClaimCheck(BaseModel):
    statement: str
    status: ClaimCheckStatus
    detail: str | None = None


class CriticFinding(BaseModel):
    category: str  # factual_grounding | numerical_consistency | unsupported_claim |
    # missing_risk | logical_consistency | confidence_calibration | ...
    severity: str = "warning"  # info | warning | critical
    detail: str


class CriticReviewOutput(BaseModel):
    verdict: Verdict
    findings: list[CriticFinding] = Field(default_factory=list)
    claim_checks: list[ClaimCheck] = Field(default_factory=list)
    deterministic_checks_passed: bool = True
    notes: str | None = None


__all__ = [
    "Assessment",
    "Catalyst",
    "ClaimCheck",
    "ClaimCheckStatus",
    "ClaimKind",
    "CriticFinding",
    "CriticReviewOutput",
    "DataQualityNote",
    "EvidenceRef",
    "FundamentalView",
    "InvalidationCondition",
    "InvestmentThesis",
    "ResearchStatement",
    "RiskItem",
    "Verdict",
]
