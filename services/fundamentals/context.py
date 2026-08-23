"""FundamentalResearchContext builder (M2, .clinerules §11/§12).

Deterministic, reproducible context assembly for the Fundamental Research
Agent. The model NEVER receives an opaque database dump: context is
assembled from typed inputs with explicit budget limits and deterministic
ranking, and carries a version + content hash so any research output can
be traced back to exactly what the model saw.

M2.1 integration: the context also carries M1 market intelligence —
normalized news (full provenance) and a bounded MarketSnapshot projection
(including discrete freshness states). Missing/stale inputs are represented
explicitly; nothing is fabricated or silently omitted.

CONTEXT_VERSION history:
- m2-v1: fundamentals/earnings/valuation/documents only.
- m2-v2: adds provenance-bearing news items, a bounded market-snapshot
  summary with freshness states, and explicit news/market_snapshot gap
  reporting. Version bumped because the hashed payload shape changed
  materially; stored m2-v1 hashes remain interpretable against v1 code.
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

CONTEXT_VERSION = "m2-v2"

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

# Mapping from the M1 FreshnessState vocabulary onto the fundamentals-domain
# DataQuality vocabulary used by data_status. Staleness is preserved via the
# detail text — never silently upgraded to OK, never treated as missing.
_FRESHNESS_TO_QUALITY: dict[str, DataQuality] = {
    "fresh": DataQuality.OK,
    "stale": DataQuality.INCOMPLETE,
    "missing": DataQuality.UNAVAILABLE,
    "invalid": DataQuality.INVALID,
}


class ContextNewsItem(BaseModel):
    """Slim, provenance-preserving news reference included in context
    (projected from the M1 normalized news store)."""

    provider_article_id: str
    headline: str
    summary: str | None = None
    source: str | None = None
    url: str | None = None
    symbols: list[str] = Field(default_factory=list)
    published_at: datetime
    received_at: datetime | None = None
    provider: str | None = None


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
    # Provenance for WHEN the snapshot view was assembled — excluded from
    # the content hash exactly like built_at (wall-clock, not data).
    market_snapshot_generated_at: datetime | None = None

    data_status: list[FundamentalDataStatus] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)  # explicit gaps

    def compute_hash(self) -> str:
        """Deterministic content hash over the canonical payload."""
        payload = self.model_dump(
            mode="json",
            exclude={"context_hash", "built_at", "market_snapshot_generated_at"},
        )
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


def _select_news(items: list[ContextNewsItem]) -> list[ContextNewsItem]:
    """Deterministic news selection (§12): dedupe by identity, newest-first
    ordering with a stable provider-article-id tie-break, then budget
    truncation. No wall-clock, no randomness, no LLM."""
    ordered = sorted(items, key=lambda n: n.provider_article_id)
    ordered.sort(key=lambda n: n.published_at, reverse=True)  # stable tie-break
    seen: set[tuple[str | None, str]] = set()
    unique: list[ContextNewsItem] = []
    for n in ordered:
        key = (n.provider, n.provider_article_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(n)
    return unique[:MAX_NEWS]


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
    news_freshness: str | None = None,
    market_snapshot_summary: dict[str, Any] | None = None,
    market_snapshot_generated_at: datetime | None = None,
    now: datetime | None = None,
) -> FundamentalResearchContext:
    """Assemble a bounded, deterministic research context.

    Ranking/filtering is fully deterministic (§12): no LLM involvement.
    `news_freshness` carries the M1 FreshnessState of the news feed
    ("fresh"|"stale"|"missing"|"invalid") as evaluated upstream against the
    same `now`. Missing inputs are recorded explicitly in `unavailable`.
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

    # --- news: deterministic selection + explicit freshness semantics -----
    news_items = _select_news(news or [])
    if not news_items:
        unavailable.append("news")
        status.append(
            FundamentalDataStatus(
                datatype="news",
                symbol=symbol.upper(),
                state=DataQuality.UNAVAILABLE,
                detail="no relevant articles available",
            )
        )
    else:
        feed_state = (news_freshness or "").strip().lower()
        quality = _FRESHNESS_TO_QUALITY.get(feed_state)
        if quality is None:
            # Freshness was not evaluated upstream — say so explicitly
            # instead of guessing (§33: no fabrication).
            status.append(
                FundamentalDataStatus(
                    datatype="news",
                    symbol=symbol.upper(),
                    state=DataQuality.INCOMPLETE,
                    detail="feed freshness not evaluated",
                )
            )
        else:
            if quality in {DataQuality.UNAVAILABLE, DataQuality.INVALID}:
                unavailable.append("news")
            status.append(
                FundamentalDataStatus(
                    datatype="news",
                    symbol=symbol.upper(),
                    state=quality,
                    detail=f"feed freshness={feed_state}",
                )
            )

    # --- market snapshot: bounded projection + explicit freshness ----------
    summary = market_snapshot_summary or {}
    if not summary:
        unavailable.append("market_snapshot")
        status.append(
            FundamentalDataStatus(
                datatype="market_snapshot",
                symbol=symbol.upper(),
                state=DataQuality.UNAVAILABLE,
                detail="no market snapshot available",
            )
        )
    else:
        overall = str(summary.get("overall_state", "")).strip().lower()
        quality = _FRESHNESS_TO_QUALITY.get(overall)
        if quality is None:
            status.append(
                FundamentalDataStatus(
                    datatype="market_snapshot",
                    symbol=symbol.upper(),
                    state=DataQuality.INCOMPLETE,
                    detail="snapshot overall_state not reported",
                )
            )
        else:
            if quality in {DataQuality.UNAVAILABLE, DataQuality.INVALID}:
                unavailable.append("market_snapshot")
            status.append(
                FundamentalDataStatus(
                    datatype="market_snapshot",
                    symbol=symbol.upper(),
                    state=quality,
                    detail=f"overall_state={overall}",
                )
            )

    ctx = FundamentalResearchContext(
        symbol=symbol.upper(),
        company_profile=profile,
        financial_metrics=selected,
        derived_metrics=derived or [],
        earnings=earnings_sorted,
        valuation=valuation,
        documents=docs,
        news=news_items,
        market_snapshot_summary=summary,
        market_snapshot_generated_at=market_snapshot_generated_at,
        data_status=status,
        unavailable=sorted(set(unavailable)),
        built_at=now,
    )
    ctx.compute_hash()
    return ctx


def render_context_for_model(ctx: FundamentalResearchContext) -> str:
    """Render the context as a compact, structured prompt block.

    Facts only — no interpretation. Unavailable fields are explicitly
    labeled so the model cannot mistake absence for zero. Every section
    renders even when its data is absent ("unavailable"), and blank lines
    separate sections.
    """
    lines: list[str] = [
        f"COMPANY: {ctx.company_profile.name if ctx.company_profile else 'UNKNOWN'} ({ctx.symbol})",
        f"CONTEXT_VERSION: {ctx.context_version}  HASH: {ctx.context_hash}",
    ]

    def section(header: str) -> None:
        # Blank separator line, then the section header.
        lines.append("")
        lines.append(header)

    if ctx.company_profile:
        p = ctx.company_profile
        lines.append(
            f"SECTOR: {p.sector or 'unavailable'} | INDUSTRY: {p.industry or 'unavailable'} "
            f"| EXCHANGE: {p.exchange or 'unavailable'} | EMPLOYEES: {p.employees or 'unavailable'}"
        )
        if p.description:
            lines.append(f"DESCRIPTION: {p.description}")

    section("FINANCIAL METRICS (deterministic source data; units as noted):")
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
        section("DERIVED METRICS (computed deterministically; formulas shown):")
        for d in ctx.derived_metrics:
            lines.append(
                f"  {d['metric']} = {d['value']:.6f}  formula: {d['formula']} "
                f"inputs: {json.dumps(d['inputs'], sort_keys=True)}"
            )

    section("EARNINGS (surprises computed deterministically):")
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
    section("VALUATION:")
    if v is None:
        lines.append("  unavailable")
    else:
        lines.append(
            f"  as_of={v.as_of.isoformat()} price={v.price or 'unavailable'} "
            f"market_cap={v.market_cap or 'unavailable'} pe={v.pe_ratio or 'unavailable'} "
            f"forward_pe={v.forward_pe or 'unavailable'} ps={v.ps_ratio or 'unavailable'} "
            f"ev_ebitda={v.ev_ebitda or 'unavailable'} fcf_yield={v.fcf_yield or 'unavailable'}"
        )

    section("RESEARCH DOCUMENTS (only these documents exist for you):")
    if not ctx.documents:
        lines.append("  unavailable")
    for doc in ctx.documents:
        lines.append(
            f"  [{doc.document_id}] {doc.title} ({doc.document_type.value}, "
            f"published={doc.published_at.date()}, source={doc.source or 'unavailable'})"
        )
        if doc.content:
            lines.append(f"    content: {doc.content}")

    section("RECENT NEWS (normalized feed; facts only — interpret, do not invent):")
    news_status = next((s for s in ctx.data_status if s.datatype == "news"), None)
    if news_status is not None and news_status.detail:
        lines.append(f"  feed_state: {news_status.detail}")
    if not ctx.news:
        lines.append("  unavailable")
    for n in ctx.news:
        received = n.received_at.date() if n.received_at else "unavailable"
        symbols = ",".join(n.symbols) if n.symbols else "unavailable"
        lines.append(
            f"  [{n.provider or 'unavailable'}:{n.provider_article_id}] "
            f"{n.published_at.date()} {n.headline} "
            f"(source={n.source or 'unavailable'}, symbols={symbols}, received={received})"
        )
        if n.summary:
            lines.append(f"    summary: {n.summary}")
        if n.url:
            lines.append(f"    url: {n.url}")

    section("MARKET SNAPSHOT (point-in-time view; freshness states are authoritative):")
    if not ctx.market_snapshot_summary:
        lines.append("  unavailable")
    else:
        s = ctx.market_snapshot_summary
        generated = (
            ctx.market_snapshot_generated_at.isoformat()
            if ctx.market_snapshot_generated_at
            else "unavailable"
        )
        lines.append(
            f"  overall_state={s.get('overall_state', 'unavailable')} generated_at={generated}"
        )
        for dq in s.get("data_quality", []):
            as_of = dq.get("as_of") or "unavailable"
            threshold = dq.get("threshold_seconds")
            threshold_s = "unavailable" if threshold is None else f"{threshold:g}s"
            detail = f" detail={dq['detail']}" if dq.get("detail") else ""
            lines.append(
                f"  {dq.get('datatype', '?')}: state={dq.get('state', 'unavailable')} "
                f"as_of={as_of} threshold={threshold_s}{detail}"
            )
        market = s.get("market") or {}
        if market:
            lines.append(f"  market: {json.dumps(market, sort_keys=True)}")

    section("DATA GAPS (explicitly unavailable — do NOT invent values for these):")
    lines.append(f"  {', '.join(ctx.unavailable) if ctx.unavailable else 'none'}")

    return chr(10).join(lines)


__all__ = [
    "CONTEXT_VERSION",
    "ContextNewsItem",
    "FundamentalResearchContext",
    "build_fundamental_context",
    "render_context_for_model",
]
