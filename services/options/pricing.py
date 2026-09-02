"""Black–Scholes–Merton pricing and Greeks (deterministic, no deps).

Implements the standard no-dividend BSM model with:
  - call / put theoretical price
  - implied volatility via bisection on the BSM price
  - all five first-order Greeks (delta, gamma, theta, vega, rho)

All functions are pure and dependency-free so the whole module is unit
testable without a network or a broker. Used by the strategy builder to
size defined-risk trades and by the risk engine to sanity-check quotes.
"""

from __future__ import annotations

import math

from options.schemas import Greeks, OptionType

_DAYS_PER_YEAR = 365.0
_IV_EPS = 1e-9
_IV_MAX_ITER = 200


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    # Abramowitz–Stegun 7.1.26 approximation; accurate to ~1e-7.
    # For x >= 0: Φ(x) = 1 - φ(x)·(b1 t + b2 t² + …); for x < 0 use symmetry.
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    phi = 0.3989422804014327 * math.exp(-x * x / 2.0)
    tail = (
        phi
        * t
        * (
            0.319381530
            + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
        )
    )
    return 1.0 - tail if x >= 0 else tail


def _d1_d2(
    spot: float,
    strike: float,
    tte: float,
    rate: float,
    vol: float,
) -> tuple[float, float]:
    if tte <= 0:
        tte = 1e-9
    if vol <= 0:
        vol = 1e-6
    sqrt_t = math.sqrt(tte)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * tte) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    return d1, d2


def black_scholes(
    spot: float,
    strike: float,
    tte: float,
    rate: float,
    vol: float,
    option_type: OptionType,
) -> float:
    """Theoretical BSM price.

    tte is time-to-expiry in years; rate is the continuous risk-free rate;
    vol is the annualized volatility (e.g. 0.30 for 30%).
    """
    if spot <= 0 or strike <= 0 or tte < 0:
        raise ValueError("spot, strike must be > 0 and tte >= 0")
    if tte == 0:
        intrinsic = (
            max(spot - strike, 0.0) if option_type == OptionType.CALL else max(strike - spot, 0.0)
        )
        return intrinsic
    d1, d2 = _d1_d2(spot, strike, tte, rate, vol)
    discount = math.exp(-rate * tte)
    if option_type == OptionType.CALL:
        return spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
    return strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def greeks(
    spot: float,
    strike: float,
    tte: float,
    rate: float,
    vol: float,
    option_type: OptionType,
) -> Greeks:
    """First-order BSM Greeks (delta, gamma, theta, vega, rho)."""
    if spot <= 0 or strike <= 0 or tte < 0:
        raise ValueError("spot, strike must be > 0 and tte >= 0")
    if tte == 0:
        return Greeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0, rho=0.0)
    d1, d2 = _d1_d2(spot, strike, tte, rate, vol)
    discount = math.exp(-rate * tte)
    pdf_d1 = _norm_pdf(d1)

    sign = 1.0 if option_type == OptionType.CALL else -1.0
    delta = sign * _norm_cdf(sign * d1)
    gamma = pdf_d1 / (spot * vol * math.sqrt(tte))
    # theta per year, then expressed per day (÷365) for interpretability.
    theta = (
        -spot * pdf_d1 * vol / (2.0 * math.sqrt(tte))
        - sign * rate * strike * discount * _norm_cdf(sign * d2)
    ) / _DAYS_PER_YEAR
    vega = spot * pdf_d1 * math.sqrt(tte) / 100.0  # per 1 vol point
    rho = sign * strike * tte * discount * _norm_cdf(sign * d2) / 100.0
    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)


def implied_volatility(
    price: float,
    spot: float,
    strike: float,
    tte: float,
    rate: float,
    option_type: OptionType,
    *,
    low: float = 1e-4,
    high: float = 5.0,
) -> float | None:
    """Bisection search for the vol that prices `price`.

    Returns None when no root exists in [low, high] (e.g. a quote below
    intrinsic value, which can happen with stale/widely-bid paper quotes).
    Callers treat None as "quote is not tradeable at a real vol" — never as 0.
    """
    if price <= 0 or spot <= 0 or strike <= 0 or tte <= 0:
        return None

    lo, hi = low, high
    if black_scholes(spot, strike, tte, rate, lo, option_type) > price:
        return None
    if black_scholes(spot, strike, tte, rate, hi, option_type) < price:
        return None

    for _ in range(_IV_MAX_ITER):
        mid = 0.5 * (lo + hi)
        val = black_scholes(spot, strike, tte, rate, mid, option_type)
        if abs(val - price) < _IV_EPS:
            return mid
        if val > price:
            hi = mid
        else:
            lo = mid
        if hi - lo < _IV_EPS:
            return 0.5 * (lo + hi)
    return 0.5 * (lo + hi)
