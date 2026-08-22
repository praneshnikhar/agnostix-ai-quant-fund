"""Financial data integrity validation (M2, .clinerules §6).

Hard requirement: numerical integrity. Questionable data is NEVER silently
corrected — it is flagged (conflicting/invalid) and preserved with
provenance. The LLM never resolves numerical conflicts.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from pydantic import BaseModel

from fundamentals.schemas import (
    DataQuality,
    EarningsEvent,
    FinancialMetric,
    FinancialPeriod,
    PeriodType,
    ValuationSnapshot,
)

# Metrics that must be non-negative when reported as a magnitude.
_NON_NEGATIVE_METRICS = frozenset(
    {
        "revenue",
        "gross_profit",
        "operating_income",
        "cash_and_equivalents",
        "total_debt",
        "shares_outstanding",
        "market_cap",
    }
)

# Metrics where negative values are economically meaningful.
_SIGNED_METRICS = frozenset({"net_income", "operating_cash_flow", "free_cash_flow"})


class IntegrityIssue(BaseModel):
    """One detected integrity problem — descriptive, never auto-corrected."""

    subject: str  # e.g. "metric:revenue:2025-12-31"
    issue: str  # machine-readable code
    detail: str


def validate_metric(metric: FinancialMetric) -> list[IntegrityIssue]:
    """Validate one metric record. Returns issues; caller flags quality."""
    issues: list[IntegrityIssue] = []
    key = f"metric:{metric.metric}:{metric.period.period_end.isoformat()}"

    if metric.value is None:
        return issues  # explicit unavailability is valid

    v = metric.value
    if v != v or v in (float("inf"), float("-inf")):
        issues.append(IntegrityIssue(subject=key, issue="non_finite", detail="value is NaN/inf"))
        return issues

    if metric.metric in _NON_NEGATIVE_METRICS and v < 0:
        issues.append(
            IntegrityIssue(
                subject=key,
                issue="negative_magnitude",
                detail=f"{metric.metric} must be >= 0, got {v}",
            )
        )
    if metric.units == "percent" and not -1000 <= v <= 1000:
        issues.append(IntegrityIssue(subject=key, issue="percent_out_of_range", detail=str(v)))

    # Timestamp validity handled by schema (tz-aware); period sanity here.
    p = metric.period
    if p.period_type == PeriodType.TTM and (
        p.fiscal_year is not None or p.fiscal_quarter is not None
    ):
        issues.append(
            IntegrityIssue(
                subject=key,
                issue="ttm_with_fiscal_ids",
                detail="TTM periods must not carry fiscal_year/fiscal_quarter",
            )
        )
    return issues


def validate_metrics(metrics: list[FinancialMetric]) -> dict[str, list[IntegrityIssue]]:
    """Validate a batch + detect duplicates/conflicts across sources.

    Returns {subject_key: [issues]}. Conflicting values for the same
    (symbol, metric, period identity) from the same provider are flagged;
    both records are preserved untouched.
    """
    out: dict[str, list[IntegrityIssue]] = defaultdict(list)
    seen: dict[tuple, list[float]] = defaultdict(list)

    for m in metrics:
        for issue in validate_metric(m):
            out[issue.subject].append(issue)
        if m.value is not None:
            ident = (
                m.symbol,
                m.metric,
                m.period.period_type,
                m.period.period_end,
                m.provider_info.provider,
            )
            seen[ident].append(m.value)

    for ident, values in seen.items():
        if len(values) > 1 and len(set(values)) > 1:
            sym, met, pt, pe, prov = ident
            key = f"conflict:{prov}:{sym}:{met}:{pt.value}:{pe.isoformat()}"
            out[key].append(
                IntegrityIssue(
                    subject=key,
                    issue="source_conflict",
                    detail=f"provider={prov} reported conflicting values {values}",
                )
            )
    return dict(out)


def flag_quality(metrics: list[FinancialMetric]) -> list[FinancialMetric]:
    """Return metrics with quality downgraded where validation found issues.

    Values are NEVER altered — only the quality marker changes.
    """
    issues = validate_metrics(metrics)
    by_subject = {i.subject for lst in issues.values() for i in lst}
    result: list[FinancialMetric] = []
    for m in metrics:
        key = f"metric:{m.metric}:{m.period.period_end.isoformat()}"
        conflict_keys = [
            k
            for k in by_subject
            if k.startswith("conflict:")
            and f":{m.symbol}:" in k
            and f":{m.metric}:" in k
            and m.period.period_end.isoformat() in k
        ]
        if any(k in by_subject for k in [key, *conflict_keys]):
            new_q = (
                DataQuality.CONFLICTING
                if any(c in by_subject for c in conflict_keys)
                else DataQuality.INVALID
            )
            result.append(m.model_copy(update={"quality": new_q}))
        else:
            result.append(m)
    return result


def validate_earnings(events: list[EarningsEvent]) -> list[IntegrityIssue]:
    """Earnings-specific checks: duplicate reporting periods per provider."""
    issues: list[IntegrityIssue] = []
    seen: set[tuple] = set()
    for e in events:
        ident = (
            e.provider_info.provider,
            e.symbol,
            e.reporting_period.period_type,
            e.reporting_period.period_end,
        )
        if ident in seen:
            issues.append(
                IntegrityIssue(
                    subject=f"earnings:{e.symbol}:{e.reporting_period.period_end}",
                    issue="duplicate_reporting_period",
                    detail=f"duplicate earnings record for {ident}",
                )
            )
        seen.add(ident)
    return issues


def validate_valuation(v: ValuationSnapshot) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []
    if v.price is not None and v.price <= 0:
        issues.append(
            IntegrityIssue(subject=f"valuation:{v.symbol}", issue="bad_price", detail="price<=0")
        )
    if v.market_cap is not None and v.shares_outstanding is not None and v.price is not None:
        implied = v.price * v.shares_outstanding
        if abs(implied - v.market_cap) / max(implied, 1e-9) > 0.05:
            issues.append(
                IntegrityIssue(
                    subject=f"valuation:{v.symbol}",
                    issue="market_cap_inconsistent",
                    detail=(
                        f"price*shares={implied:.2f} differs from market_cap="
                        f"{v.market_cap:.2f} by >5%"
                    ),
                )
            )
    return issues


def check_currency_consistency(records_currency: str, expected: str = "USD") -> bool:
    """Currency consistency gate for context assembly."""
    return records_currency.upper() == expected.upper()


def period_sort_key(p: FinancialPeriod) -> tuple[date, str]:
    """Deterministic ordering: by period end, then period type."""
    return (p.period_end, p.period_type.value)
