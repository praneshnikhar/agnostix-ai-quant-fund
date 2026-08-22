"""FundamentalResearchContext builder (M2, .clinerules §11/§12).

Deterministic, reproducible context assembly for the Fundamental Research
Agent. The model NEVER receives an opaque database dump: context is
assembled from typed inputs with explicit budget limits and deterministic
ranking, and carries a version + content hash so any research output can
be traced back to exactly what the model saw.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from fundamentals.schemas import (
    CompanyProfile,
    DataQuality,
    EarningsResult,
    FinancialMetric,
    FundamentalDataStatus,
    ResearchDocument,
    ValuationSnapshot,
)
from fundamentals.validation import period_sort_key

CONTEXT_VERSION = "m2-v1"

# Deterministic context budget (§12): bounded, prioritized slices.
MAX_ANNUAL_PERIODS = 5
MAX_QUARTER_PERIODS = 4
MAX_EARNINGS_EVENTS = 4
MAX_DOCUMENTS = 5
MAX_NEWS = 5
MAX_METRIC_NAMES = 20

# Deterministic document ranking weights (recency + type priority).
_DOC_TYPE_PRIORITY = {
    "filing": 3,
    "earnings_release": 3,
    "transcript": 2,
    "ir_presentation": 1,
    "announcement": 1,
    "news": 0,
}


class ContextNewsItem(BaseModel):
    """Slim news reference included in context (from M1 news store)."""

    headline: str
    source: str | None = None
    published_at: datetime
    url: str | None = None


class FundamentalResearchContext(BaseModel):
    """Exactly what the research model receives — nothing more."""

    context_version: str = CONTEXT_VERSION
    context_hash: str = ""
    built_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    symbol: str

    company_profile: CompanyProfile | None = None
    financial_metrics: list[FinancialMetric] = Field(default_factory=list)
    derived_metrics: list[dict[str, Any]] = Field(default_factory=list)
    earnings: list[EarningsResult] = Field(default_factory=list)
    valuation: ValuationSnapshot | None = None
    documents: list[ResearchDocument] = Field(default_factory=list)
    news: list[ContextNewsItem] = Field(default_factory=list)
    market_snapshot_summary: dict[str, Any] = Field(default_factory=dict)

    data_status: list[FundamentalDataStatus] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)  # explicit gaps

    def compute_hash(self) -> str:
        """Deterministic content hash over the canonical payload."""
        payload = self.model_dump(mode="json", exclude={"context_hash", "built_at"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self.context_hash = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        return self.context_hash


def _rank_documents(docs: list[ResearchDocument], now: datetime) -> list[ResearchDocument]:
    """Deterministic ranking: type priority desc, then recency desc, then id."""
    del now  # ranking is deterministic on published_at; `now` reserved for future decay
    return sorted(
        docs,
        key=lambda d: (
            _DOC_TYPE_PRIORITY.get(d.document_type.value, 0),
            d.published_at,
            d.document_id,
        ),
        reverse=True,
    )


def build_fundamental_context(
    symbol: str,
    *,
    profile: CompanyProfile | None,
    metrics: list[FinancialMetric],
    derived: list[dict[str, Any]] | None = None,
    earnings: list[EarningsResult] | None = None,
    valuation: ValuationSnapshot | None = None,
    documents: list[ResearchDocument] | None = None,
    news: list[ContextNewsItem] | None = None,
    market_snapshot_summary: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> FundamentalResearchContext:
    """Assemble a bounded, deterministic research context.

    Ranking/filtering is fully deterministic (§12): no LLM involvement.
    Missing inputs are recorded explicitly in `unavailable`.
    """
    now = now or datetime.now(UTC)
    unavailable: list[str] = []
    status: list[FundamentalDataStatus] = []

    # --- metrics: latest N annual + latest M quarterly periods only -------
    annual = sorted(
        (m for m in metrics if m.period.period_type.value == "annual"),
        key=lambda m: period_sort_key(m.period),
        reverse=True,
    )
    quarterly = sorted(
        (m for m in metrics if m.period.period_type.value == "quarterly"),
        key=lambda m: period_sort_key(m.period),
        reverse=True,
    )
    top_annual_ends = list({m.period.period_end for m in annual})[:MAX_ANNUAL_PERIODS]
    top_q_ends = list({m.period.period_end for m in quarterly})[:MAX_QUARTER_PERIODS]
    selected = [m for m in annual if m.period.period_end in top_annual_ends] + [
        m for m in quarterly if m.period.period_end in top_q_ends
    ]
    # deterministic order: period end desc, metric name asc
    selected.sort(key=lambda m: (m.period.period_end, m.metric), reverse=True)
    metric_names = {m.metric for m in selected}
    if len(metric_names) > MAX_METRIC_NAMES:
        keep = sorted(metric_names)[:MAX_METRIC_NAMES]
        selected = [m for m in selected if m.metric in keep]

    if profile is None:
        unavailable.append("company_profile")
        status.append(
            FundamentalDataStatus(
                datatype="profile", symbol=symbol.upper(), state=DataQuality.UNAVAILABLE
            )
        )
    else:
        status.append(
            FundamentalDataStatus(datatype="profile", symbol=symbol.upper(), state=DataQuality.OK)
        )

    status.append(
        FundamentalDataStatus(
            datatype="metrics",
            symbol=symbol.upper(),
            state=DataQuality.OK if selected else DataQuality.UNAVAILABLE,
        )
    )
    if not selected:
        unavailable.append("financial_metrics")

    earnings = earnings or []
    earnings_sorted = sorted(earnings, key=lambda e: e.event.event_time, reverse=True)[
        :MAX_EARNINGS_EVENTS
    ]
    if not earnings_sorted:
        unavailable.append("earnings")
        status.append(
            FundamentalDataStatus(
                datatype="earnings", symbol=symbol.upper(), state=DataQuality.UNAVAILABLE
            )
        )
    else:
        status.append(
            FundamentalDataStatus(datatype="earnings", symbol=symbol.upper(), state=DataQuality.OK)
        )

    if valuation is None:
        unavailable.append("valuation")
        status.append(
            FundamentalDataStatus(
                datatype="valuation", symbol=symbol.upper(), state=DataQuality.UNAVAILABLE
            )
        )
    else:
        status.append(
            FundamentalDataStatus(datatype="valuation", symbol=symbol.upper(), state=DataQuality.OK)
        )

    docs = _rank_documents(documents or [], now)[:MAX_DOCUMENTS]
    if not docs:
        unavailable.append("research_documents")
        status.append(
            FundamentalDataStatus(
                datatype="documents", symbol=symbol.upper(), state=DataQuality.UNAVAILABLE
            )
        )
    else:
        status.append(
            FundamentalDataStatus(datatype="documents", symbol=symbol.upper(), state=DataQuality.OK)
        )

    news_items = (news or [])[:MAX_NEWS]

    ctx = FundamentalResearchContext(
        symbol=symbol.upper(),
        company_profile=profile,
        financial_metrics=selected,
        derived_metrics=derived or [],
        earnings=earnings_sorted,
        valuation=valuation,
        documents=docs,
        news=news_items,
        market_snapshot_summary=market_snapshot_summary or {},
        data_status=status,
        unavailable=sorted(set(unavailable)),
        built_at=now,
    )
    ctx.compute_hash()
    return ctx


def render_context_for_model(ctx: FundamentalResearchContext) -> str:
    """Render the context as a compact, structured prompt block.

    Facts only — no interpretation. Unavailable fields are explicitly
    labeled so the model cannot mistake absence for zero.
    """
    lines: list[str] = [
        f"COMPANY: {ctx.company_profile.name if ctx.company_profile else 'UNKNOWN'} ({ctx.symbol})",
        f"CONTEXT_VERSION: {ctx.context_version}  HASH: {ctx.context_hash}",
    ]
    if ctx.company_profile:
        p = ctx.company_profile
        lines.append(
            f"SECTOR: {p.sector or 'unavailable'} | INDUSTRY: {p.industry or 'unavailable'} "
            f"| EXCHANGE: {p.exchange or 'unavailable'} | EMPLOYEES: {p.employees or 'unavailable'}"
        )
        if p.description:
            lines.append(f"DESCRIPTION: {p.description}")

    lines.append("\nFINANCIAL METRICS (deterministic source data; units as noted):")
    if not ctx.financial_metrics:
        lines.append("  unavailable")
    for m in ctx.financial_metrics:
        per = m.period
        ident = (
            f"FY{per.fiscal_year}"
            if per.period_type.value == "annual"
            else f"FY{per.fiscal_year}Q{per.fiscal_quarter}"
        )
        val = "unavailable" if m.value is None else f"{m.value:,.4f}"
        lines.append(
            f"  {m.metric} [{per.period_type.value} {ident} end={per.period_end}] = {val} "
            f"({m.units}, source={m.provider_info.provider}, quality={m.quality.value})"
        )

    if ctx.derived_metrics:
        lines.append("\nDERIVED METRICS (computed deterministically; formulas shown):")
        for d in ctx.derived_metrics:
            lines.append(
                f"  {d['metric']} = {d['value']:.6f}  formula: {d['formula']} "
                f"inputs: {json.dumps(d['inputs'], sort_keys=True)}"
            )

    lines.append("\nEARNINGS (surprises computed deterministically):")
    if not ctx.earnings:
        lines.append("  unavailable")
    for e in ctx.earnings:
        ev = e.event
        rp = ev.reporting_period
        lines.append(
            f"  period=FY{rp.fiscal_year}Q{rp.fiscal_quarter} end={rp.period_end} "
            f"reported={ev.event_time.isoformat()} "
            f"eps actual={'unavailable' if ev.eps_actual is None else ev.eps_actual} "
            f"estimate={'unavailable' if ev.eps_estimate is None else ev.eps_estimate} "
            f"surprise={'unavailable' if e.eps_surprise is None else e.eps_surprise} "
            f"revenue actual={'unavailable' if ev.revenue_actual is None else ev.revenue_actual} "
            f"estimate={'unavailable' if ev.revenue_estimate is None else ev.revenue_estimate}"
        )

    v = ctx.valuation
    lines.append("\nVALUATION:")
    if v is None:
        lines.append("  unavailable")
    else:
        lines.append(
            f"  as_of={v.as_of.isoformat()} price={v.price or 'unavailable'} "
            f"market_cap={v.market_cap or 'unavailable'} pe={v.pe_ratio or 'unavailable'} "
            f"forward_pe={v.forward_pe or 'unavailable'} ps={v.ps_ratio or 'unavailable'} "
            f"ev_ebitda={v.ev_ebitda or 'unavailable'} fcf_yield={v.fcf_yield or 'unavailable'}"
        )

    lines.append("\nRESEARCH DOCUMENTS (only these documents exist for you):")
    if not ctx.documents:
        lines.append("  unavailable")
    for doc in ctx.documents:
        lines.append(
            f"  [{doc.document_id}] {doc.title} ({doc.document_type.value}, "
            f"published={doc.published_at.date()}, source={doc.source or 'unavailable'})"
        )
        if doc.content:
            lines.append(f"    content: {doc.content}")

    if ctx.news:
        lines.append("\nRECENT NEWS:")
        for n in ctx.news:
            lines.append(
                f"  {n.published_at.date()} {n.headline} (source={n.source or 'unavailable'})"
            )

    if ctx.market_snapshot_summary:
        lines.append(
            f"\nMARKET SNAPSHOT: {json.dumps(ctx.market_snapshot_summary, sort_keys=True)}"
        )

    lines.append("\nDATA GAPS (explicitly unavailable — do NOT invent values for these):")
    lines.append(f"  {', '.join(ctx.unavailable) if ctx.unavailable else 'none'}")

    return "\n".join(lines)


__all__ = [
    "CONTEXT_VERSION",
    "ContextNewsItem",
    "FundamentalResearchContext",
    "build_fundamental_context",
    "render_context_for_model",
]
