"""Options market context — deterministic enrichment of raw chains.

Takes raw contracts + quotes from a broker and produces a fully-priced,
Greeks-complete chain using the local Black–Scholes engine. This makes the
strategy builder work even when the broker's OPRA feed omits Greeks or IV
(common in paper accounts), and guarantees every number is reproducible.

Realized-volatility analytics are provided as an honest, dependency-free
proxy for IV rank when an IV history is not available.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from options.pricing import greeks, implied_volatility
from options.schemas import OptionQuote, OptionType

DEFAULT_RISK_FREE_RATE = 0.04


def _now() -> datetime:
    return datetime.now(UTC)


def _tte(expiration: datetime) -> float:
    return max((expiration - _now()).total_seconds() / (365.0 * 86400.0), 1e-6)


def enrich_quote(
    quote: OptionQuote,
    spot: float,
    strike: float,
    expiration: datetime,
    option_type: OptionType,
    *,
    rate: float = DEFAULT_RISK_FREE_RATE,
) -> OptionQuote:
    """Fill in missing IV + Greeks with deterministic BSM values.

    IV is backed out of the quote mid (or last) using bisection; if no
    tradeable mid exists, IV/Greeks are computed from a realized-vol proxy
    supplied by the caller via `quote.implied_volatility` when present.
    Never fabricates a quote — if the option is untradeable, IV stays None.
    """
    mid = None
    if quote.bid is not None and quote.ask is not None:
        mid = (quote.bid + quote.ask) / 2.0
    elif quote.last is not None:
        mid = quote.last

    tte = _tte(expiration)
    iv = quote.implied_volatility
    if mid is not None and mid > 0:
        iv = implied_volatility(mid, spot, strike, tte, rate, option_type) or iv

    if iv is not None and iv > 0:
        g = greeks(spot, strike, tte, rate, iv, option_type)
        return quote.model_copy(
            update={
                "implied_volatility": iv,
                "delta": quote.delta if quote.delta is not None else g.delta,
                "gamma": quote.gamma if quote.gamma is not None else g.gamma,
                "theta": quote.theta if quote.theta is not None else g.theta,
                "vega": quote.vega if quote.vega is not None else g.vega,
            }
        )
    return quote


def realized_volatility(
    closes: list[float], *, window: int = 30, periods: int = 252
) -> float | None:
    """Annualized realized volatility from a series of daily closes."""
    closes = [c for c in closes if c is not None and c > 0]
    if len(closes) < window + 1:
        return None
    window = min(window, len(closes) - 1)
    recent = closes[-(window + 1) :]
    returns = [math.log(recent[i] / recent[i - 1]) for i in range(1, len(recent))]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(periods)


def volatility_rank(
    current_vol: float | None,
    closes: list[float],
    *,
    window: int = 30,
    periods: int = 252,
    history_windows: int = 24,
) -> float | None:
    """Percentile of current realized vol within a rolling realized-vol series.

    Builds up to `history_windows` overlapping `window`-day realized-vol
    observations from the close history, then ranks `current_vol` among them.
    Returns None when the history is too short to be meaningful.
    """
    from options.iv import iv_percentile

    if current_vol is None or current_vol <= 0:
        return None
    closes = [c for c in closes if c is not None and c > 0]
    if len(closes) < window + 2:
        return None
    series: list[float] = []
    # slide the window back to build a small history of realized vols
    for offset in range(0, min(history_windows, len(closes) - window)):
        seg = closes[: len(closes) - offset]
        rv = realized_volatility(seg, window=window, periods=periods)
        if rv is not None and rv > 0:
            series.append(rv)
    if len(series) < 5:
        return None
    return iv_percentile(current_vol, series)
