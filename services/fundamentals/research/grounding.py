"""Deterministic grounding checks (M2, .clinerules §20).

The critic must NOT depend on another LLM to catch obvious numerical
inconsistencies. These checks are pure functions over (context, thesis):

- every evidence_id must exist in the context (documents/metrics/earnings)
- numeric claims in FACT statements must be traceable to context values
- fundamental_view must use the constrained vocabulary (schema-enforced)
- INSUFFICIENT_DATA must be used when key data is unavailable
"""

from __future__ import annotations

import re
from typing import Any

from fundamentals.context import FundamentalResearchContext, render_context_for_model
from fundamentals.research.schemas import (
    ClaimCheck,
    ClaimCheckStatus,
    CriticFinding,
    InvestmentThesis,
)

_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")

# Tolerance for float formatting differences when matching context values.
_REL_TOL = 0.005


def _context_numbers(ctx: FundamentalResearchContext) -> set[float]:
    """All numeric values the model was actually given."""
    vals: set[float] = set()
    for m in ctx.financial_metrics:
        if m.value is not None:
            vals.add(abs(m.value))
    for d in ctx.derived_metrics:
        vals.add(abs(float(d["value"])))
        for inp in d.get("inputs", []):
            if inp.get("value") is not None:
                vals.add(abs(float(inp["value"])))
    for e in ctx.earnings:
        ev = e.event
        for v in (ev.eps_actual, ev.eps_estimate, ev.revenue_actual, ev.revenue_estimate,
                  e.eps_surprise, e.eps_surprise_pct, e.revenue_surprise, e.revenue_surprise_pct):
            if v is not None:
                vals.add(abs(v))
    v = ctx.valuation
    if v is not None:
        for x in (v.price, v.market_cap, v.pe_ratio, v.forward_pe, v.ps_ratio,
                  v.ev_ebitda, v.fcf_yield, v.shares_outstanding):
            if x is not None:
                vals.add(abs(x))
    if ctx.company_profile and ctx.company_profile.employees:
        vals.add(float(ctx.company_profile.employees))
    return vals


def _is_grounded(number: float, context_values: set[float], rendered: str) -> bool:
    """A number is grounded if it matches a context value within tolerance
    OR appears verbatim in the rendered context (dates, fiscal years, etc.)."""
    n = abs(number)
    for cv in context_values:
        if cv == 0:
            if n == 0:
                return True
            continue
        if abs(n - cv) / cv <= _REL_TOL:
            return True
    # Verbatim presence via word-boundary regex (avoids "42" matching
    # inside "142" or "0.4200"). Covers common render formats.
    candidates = {
        re.escape(f"{number}"),
        re.escape(f"{number:.2f}"),
        re.escape(f"{number:,.2f}"),
        re.escape(f"{number:,.4f}"),
        re.escape(f"{int(number):,}") if number == int(number) else None,
    }
    for cand in candidates:
        if cand and re.search(rf"(?<![\d.,]){cand}(?![\d])", rendered):
            return True
    return False


def check_evidence_existence(
    thesis: InvestmentThesis, ctx: FundamentalResearchContext
) -> list[ClaimCheck]:
    """Every referenced evidence_id must exist in the context."""
    known: set[str] = {d.document_id for d in ctx.documents}
    for m in ctx.financial_metrics:
        if m.provider_info.raw_record_id:
            known.add(m.provider_info.raw_record_id)
    for e in ctx.earnings:
        if e.event.provider_info.raw_record_id:
            known.add(e.event.provider_info.raw_record_id)
    if ctx.valuation and ctx.valuation.provider_info.raw_record_id:
        known.add(ctx.valuation.provider_info.raw_record_id)

    checks: list[ClaimCheck] = []
    for ev in thesis.evidence:
        ok = ev.source in known or ev.evidence_id in known
        checks.append(
            ClaimCheck(
                statement=f"evidence:{ev.evidence_id}",
                status=ClaimCheckStatus.SUPPORTED if ok else ClaimCheckStatus.UNSUPPORTED,
                detail=None if ok else f"evidence source '{ev.source}' not present in context",
            )
        )
    return checks


def check_numerical_grounding(
    thesis: InvestmentThesis, ctx: FundamentalResearchContext
) -> tuple[list[ClaimCheck], list[CriticFinding]]:
    """Numbers in FACT statements must be traceable to the context."""
    context_values = _context_numbers(ctx)
    rendered = render_context_for_model(ctx)
    checks: list[ClaimCheck] = []
    findings: list[CriticFinding] = []

    statements: list[tuple[str, str]] = []
    for area in (
        thesis.financial_assessment, thesis.growth_assessment,
        thesis.profitability_assessment, thesis.cash_flow_assessment,
        thesis.balance_sheet_assessment, thesis.valuation_assessment,
    ):
        for s in area.statements:
            statements.append((f"{area.area}/{s.kind.value}", s.text))
    for cat in thesis.catalysts:
        statements.append(("catalyst", cat.description))
    for r in thesis.risks:
        statements.append(("risk", r.description))

    for where, text in statements:
        if not text:
            continue
        # Only FACT-kind statements are held to strict numeric grounding;
        # interpretations may reference derived comparisons.
        is_fact = "/FACT" in where
        numbers = [float(x.replace(",", "")) for x in _NUMBER_RE.findall(text)]
        # Ignore years and small integers that are likely counts/ordinals.
        numbers = [n for n in numbers if not (1900 <= n <= 2100)]
        if not numbers:
            continue
        ungrounded = [n for n in numbers if not _is_grounded(n, context_values, rendered)]
        if ungrounded and is_fact:
            checks.append(
                ClaimCheck(
                    statement=f"{where}: {text[:200]}",
                    status=ClaimCheckStatus.CONTRADICTED,
                    detail=f"numbers not traceable to context: {ungrounded}",
                )
            )
            findings.append(
                CriticFinding(
                    category="numerical_consistency",
                    severity="critical",
                    detail=(
                        f"FACT statement in {where} contains numbers not present in "
                        f"context: {ungrounded}"
                    ),
                )
            )
        elif ungrounded:
            checks.append(
                ClaimCheck(
                    statement=f"{where}: {text[:200]}",
                    status=ClaimCheckStatus.UNSUPPORTED,
                    detail=f"interpretation references numbers not in context: {ungrounded}",
                )
            )
        else:
            checks.append(ClaimCheck(statement=f"{where}: {text[:200]}", status=ClaimCheckStatus.SUPPORTED))
    return checks, findings


def check_insufficient_data_handling(
    thesis: InvestmentThesis, ctx: FundamentalResearchContext
) -> list[CriticFinding]:
    """If key data is unavailable, the agent must not claim high confidence
    or a strong view without acknowledging the gap."""
    findings: list[CriticFinding] = []
    if ctx.unavailable and thesis.fundamental_view.value in {"BULLISH", "BEARISH"}:
        if thesis.confidence > 0.8:
            findings.append(
                CriticFinding(
                    category="confidence_calibration",
                    severity="warning",
                    detail=(
                        f"high confidence ({thesis.confidence}) despite unavailable data: "
                        f"{ctx.unavailable}"
                    ),
                )
            )
    if not ctx.financial_metrics and thesis.fundamental_view.value != "INSUFFICIENT_DATA":
        findings.append(
            CriticFinding(
                category="factual_grounding",
                severity="critical",
                detail="no financial metrics in context but a directional view was issued",
            )
        )
    return findings


def run_deterministic_checks(
    thesis: InvestmentThesis, ctx: FundamentalResearchContext
) -> dict[str, Any]:
    """Full deterministic check suite. Returns structured results; the
    critic combines these with (optional) LLM review — deterministic
    failures are authoritative."""
    evidence_checks = check_evidence_existence(thesis, ctx)
    numeric_checks, numeric_findings = check_numerical_grounding(thesis, ctx)
    calibration_findings = check_insufficient_data_handling(thesis, ctx)

    failed = any(
        c.status in {ClaimCheckStatus.CONTRADICTED, ClaimCheckStatus.UNSUPPORTED}
        for c in evidence_checks + numeric_checks
    )
    critical = [f for f in numeric_findings + calibration_findings if f.severity == "critical"]

    return {
        "claim_checks": [c.model_dump() for c in evidence_checks + numeric_checks],
        "findings": [f.model_dump() for f in numeric_findings + calibration_findings],
        "passed": not failed and not critical,
        "unsupported_count": sum(
            1 for c in evidence_checks + numeric_checks
            if c.status == ClaimCheckStatus.UNSUPPORTED
        ),
        "contradicted_count": sum(
            1 for c in evidence_checks + numeric_checks
            if c.status == ClaimCheckStatus.CONTRADICTED
        ),
    }


__all__ = ["run_deterministic_checks"]