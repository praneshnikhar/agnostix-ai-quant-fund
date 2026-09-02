"""Unit tests for options pricing and implied volatility (no network)."""

from __future__ import annotations

import math

import pytest

from options.pricing import black_scholes, greeks, implied_volatility
from options.schemas import OptionType

# Known BSM reference values (spot 100, strike 100, tte 1y, r=5%, vol=20%).
# Computed from the standard closed-form; tolerances are loose to absorb the
# CDF approximation error (~1e-7 is fine; use 1e-4 for price sanity).
SPOT, STRIKE, TTE, RATE, VOL = 100.0, 100.0, 1.0, 0.05, 0.20


def test_call_put_parity() -> None:
    call = black_scholes(SPOT, STRIKE, TTE, RATE, VOL, OptionType.CALL)
    put = black_scholes(SPOT, STRIKE, TTE, RATE, VOL, OptionType.PUT)
    # C - P = S - K e^{-rT}
    parity = SPOT - STRIKE * math.exp(-RATE * TTE)
    assert call - put == pytest.approx(parity, rel=1e-4)


def test_call_known_value() -> None:
    call = black_scholes(SPOT, STRIKE, TTE, RATE, VOL, OptionType.CALL)
    assert call == pytest.approx(10.45, abs=0.05)


def test_put_known_value() -> None:
    put = black_scholes(SPOT, STRIKE, TTE, RATE, VOL, OptionType.PUT)
    assert put == pytest.approx(5.57, abs=0.05)


def test_intrinsic_at_expiry() -> None:
    assert black_scholes(110.0, 100.0, 0.0, RATE, VOL, OptionType.CALL) == pytest.approx(10.0)
    assert black_scholes(90.0, 100.0, 0.0, RATE, VOL, OptionType.PUT) == pytest.approx(10.0)


def test_greeks_signs() -> None:
    g = greeks(SPOT, STRIKE, TTE, RATE, VOL, OptionType.CALL)
    assert 0.0 < g.delta < 1.0
    assert g.gamma > 0.0
    assert g.theta < 0.0  # long option loses value each day
    assert g.vega > 0.0
    assert g.rho > 0.0


def test_put_delta_negative() -> None:
    g = greeks(SPOT, STRIKE, TTE, RATE, VOL, OptionType.PUT)
    assert -1.0 < g.delta < 0.0


def test_atm_call_delta_about_half() -> None:
    g = greeks(SPOT, STRIKE, TTE, RATE, VOL, OptionType.CALL)
    assert g.delta == pytest.approx(0.63, abs=0.02)


def test_implied_vol_roundtrip() -> None:
    price = black_scholes(SPOT, STRIKE, TTE, RATE, VOL, OptionType.CALL)
    iv = implied_volatility(price, SPOT, STRIKE, TTE, RATE, OptionType.CALL)
    assert iv is not None
    assert iv == pytest.approx(VOL, abs=1e-4)


def test_implied_vol_below_intrinsic_returns_none() -> None:
    # A call at spot 100 / strike 90 must be worth ≥ 10; a price of 5 is
    # below intrinsic, so no real vol exists — must return None, not 0.
    iv = implied_volatility(5.0, 100.0, 90.0, 0.25, RATE, OptionType.CALL)
    assert iv is None


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        black_scholes(-1.0, STRIKE, TTE, RATE, VOL, OptionType.CALL)
    with pytest.raises(ValueError):
        greeks(SPOT, STRIKE, -0.1, RATE, VOL, OptionType.CALL)
