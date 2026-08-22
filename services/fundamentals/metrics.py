"""Deterministic derived metrics (M2, .clinerules §6/§7).

ALL financial arithmetic lives here — never in an LLM. Every derived value
carries formula + inputs + source + calculation timestamp so it is fully
reproducible. Metrics are computed only from complete inputs; incomplete
data yields None (explicit unavailability), never a partial guess.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fundamentals.schemas import DerivedMetric, FinancialMetric, PeriodType


def _index(metrics: list[FinancialMetric]) -> dict[tuple[str, str, str], FinancialMetric]:
    """(metric, period_type, period_end ISO) -> metric."""
    return {
        (m.metric, m.period.period_type.value, m.period.period_end.isoformat()): m
        for m in metrics
        if m.value is not None and m.quality.value == "ok"
    }


def _get(
    idx: dict[tuple[str, str, str], FinancialMetric],
    symbol: str,
    metric: str,
    period_type: PeriodType,
    period_end,
) -> FinancialMetric | None:
    return idx.get((metric, period_type.value, period_end.isoformat()))


def _derive(
    symbol: str,
    name: str,
    formula: str,
    inputs: list[FinancialMetric],
    compute,
) -> DerivedMetric | None:
    """Run `compute` over input values; None inputs => unavailable result."""
    if any(i is None for i in inputs):
        return None
    values = [i.value for i in inputs]
    assert all(v is not None for v in values)
    try:
        value = compute(*values)  # type: ignore[misc]
    except ZeroDivisionError:
        return None
    if value is None or value != value:
        return None
    return DerivedMetric(
        symbol=symbol,
        metric=name,
        value=round(value, 6),
        formula=formula,
        inputs=[
            {
                "metric": i.metric,
                "period_type": i.period.period_type.value,
                "period_end": i.period.period_end.isoformat(),
                "value": i.value,
                "provider": i.provider_info.provider,
            }
            for i in inputs
        ],
        calculated_at=datetime.now(UTC),
    )


def revenue_growth_yoy(
    metrics: list[FinancialMetric],
    current_period_end,
    prior_period_end,
    period_type: PeriodType = PeriodType.ANNUAL,
) -> DerivedMetric | None:
    """YoY revenue growth: (rev_t - rev_prior) / |rev_prior|."""
    idx = _index(metrics)
    cur = _get(idx, metrics[0].symbol if metrics else "", "revenue", period_type, current_period_end)
    pri = _get(idx, metrics[0].symbol if metrics else "", "revenue", period_type, prior_period_end)
    if cur is None or pri is None:
        return None
    return _derive(
        cur.symbol,
        "revenue_growth_yoy",
        "(revenue_t - revenue_prior) / abs(revenue_prior)",
        [cur, pri],
        lambda c, p: (c - p) / abs(p),
    )


def margin(
    metrics: list[FinancialMetric],
    numerator_metric: str,
    period_end,
    period_type: PeriodType = PeriodType.ANNUAL,
) -> DerivedMetric | None:
    """Generic margin: numerator / revenue for the same period."""
    sym = metrics[0].symbol if metrics else ""
    idx = _index(metrics)
    num = _get(idx, sym, numerator_metric, period_type, period_end)
    rev = _get(idx, sym, "revenue", period_type, period_end)
    if num is None or rev is None:
        return None
    return _derive(
        sym,
        f"{numerator_metric}_margin",
        f"{numerator_metric} / revenue",
        [num, rev],
        lambda n, r: n / r,
    )


def net_debt(
    metrics: list[FinancialMetric],
    period_end,
    period_type: PeriodType = PeriodType.QUARTERLY,
) -> DerivedMetric | None:
    """Net debt: total_debt - cash_and_equivalents."""
    sym = metrics[0].symbol if metrics else ""
    idx = _index(metrics)
    debt = _get(idx, sym, "total_debt", period_type, period_end)
    cash = _get(idx, sym, "cash_and_equivalents", period_type, period_end)
    if debt is None or cash is None:
        return None
    return _derive(
        sym,
        "net_debt",
        "total_debt - cash_and_equivalents",
        [debt, cash],
        lambda d, c: d - c,
    )


def free_cash_flow(
    metrics: list[FinancialMetric],
    period_end,
    period_type: PeriodType = PeriodType.ANNUAL,
) -> DerivedMetric | None:
    """FCF: operating_cash_flow - capital_expenditure."""
    sym = metrics[0].symbol if metrics else ""
    idx = _index(metrics)
    ocf = _get(idx, sym, "operating_cash_flow", period_type, period_end)
    capex = _get(idx, sym, "capital_expenditure", period_type, period_end)
    if ocf is None or capex is None:
        return None
    return _derive(
        sym,
        "free_cash_flow",
        "operating_cash_flow - capital_expenditure",
        [ocf, capex],
        lambda o, c: o - c,
    )


def earnings_surprise(actual: float | None, estimate: float | None) -> tuple[float | None, float | None]:
    """Deterministic surprise: (actual-estimate, surprise/|estimate|).

    Returns (None, None) when either input is missing — no guessing.
    """
    if actual is None or estimate is None or estimate == 0:
        return (None, None)
    surprise = actual - estimate
    pct = surprise / abs(estimate)
    return (round(surprise, 6), round(pct, 6))


__all__ = [
    "earnings_surprise",
    "free_cash_flow",
    "margin",
    "net_debt",
    "revenue_growth_yoy",
]