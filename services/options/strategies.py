"""Defined-risk option strategy construction.

The pattern this module enforces is the core safety property of the whole
trading agent:

    LLM proposes a DIRECTION + thesis.
    THIS CODE (deterministic) picks every strike, width, and size.

No model ever chooses a strike, quantity, or leg structure. Strategies are
constructed from a real option chain and always produce a finite, pre-computed
`max_loss` (defined risk). Pure functions only — no broker, no LLM.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from options.pricing import black_scholes
from options.schemas import (
    OptionContract,
    OptionLeg,
    OptionQuote,
    OptionSide,
    OptionStrategy,
    OptionType,
)

DIRECTION = str  # "bullish" | "bearish" | "neutral"


def _now() -> datetime:
    return datetime.now(UTC)


def _mid(quote: OptionQuote) -> float | None:
    if quote.bid is not None and quote.ask is not None:
        return (quote.bid + quote.ask) / 2.0
    return quote.last


def _sort_puts(puts: list[OptionQuote]) -> list[OptionQuote]:
    return sorted(puts, key=lambda q: q.strike)


def _sort_calls(calls: list[OptionQuote]) -> list[OptionQuote]:
    return sorted(calls, key=lambda q: q.strike)


def _pick_by_delta(
    quotes: list[OptionQuote],
    target_delta: float,
    *,
    sell: bool,
) -> OptionQuote | None:
    """Pick the option whose |delta| is closest to `target_delta`.

    For a short leg we target the strike whose delta magnitude is just below
    the target (conservative — more OTM); for a long leg we target closest.
    Returns None if the chain has no usable quotes.
    """
    usable = [q for q in quotes if q.delta is not None]
    if not usable:
        return None

    def _key(q: OptionQuote) -> float:
        return (abs(q.delta or 0.0) - target_delta) ** 2

    return sorted(usable, key=_key)[0]


def _contract(
    quote: OptionQuote, underlying: str, option_type: OptionType, expiration: datetime
) -> OptionContract:
    return OptionContract(
        symbol=quote.symbol,
        underlying=underlying,
        option_type=option_type,
        strike=quote.strike,
        expiration=expiration,
    )


def bull_put_spread(
    underlying: str,
    spot: float,
    expiration: datetime,
    puts: list[OptionQuote],
    *,
    short_delta: float = 0.30,
    width_strikes: int = 1,
    quantity: int = 1,
) -> OptionStrategy | None:
    """Sell an OTM put spread (bullish / neutral income).

    Short strike ≈ target delta; long strike `width_strikes` further OTM
    (lower strike). Max loss = (width × 100 − net credit) per contract.
    """
    ordered = _sort_puts(puts)
    short = _pick_by_delta(ordered, short_delta, sell=True)
    if short is None:
        return None
    short_idx = ordered.index(short)
    long_idx = short_idx - width_strikes
    if long_idx < 0:
        return None
    long = ordered[long_idx]

    short_mid = _mid(short) or 0.0
    long_mid = _mid(long) or 0.0
    net_credit = max(short_mid - long_mid, 0.0)
    width = short.strike - long.strike

    legs = [
        OptionLeg(
            contract=_contract(short, underlying, OptionType.PUT, expiration),
            side=OptionSide.SELL_TO_OPEN,
            quantity=quantity,
            theoretical=short_mid,
            delta=short.delta,
        ),
        OptionLeg(
            contract=_contract(long, underlying, OptionType.PUT, expiration),
            side=OptionSide.BUY_TO_OPEN,
            quantity=quantity,
            theoretical=long_mid,
            delta=long.delta,
        ),
    ]
    max_loss = width * 100.0 * quantity - net_credit * 100.0 * quantity
    max_profit = net_credit * 100.0 * quantity
    pop = 1.0 - (short.delta if short.delta is not None else short_delta)

    return OptionStrategy(
        strategy_id=f"bps-{uuid.uuid4().hex[:12]}",
        name="bull_put_spread",
        underlying=underlying,
        legs=legs,
        net_credit=net_credit,
        max_loss=max_loss,
        max_profit=max_profit,
        break_even=[short.strike - net_credit],
        probability_of_profit=round(max(0.0, min(1.0, pop)), 4),
        days_to_expiration=max(0, (expiration - _now()).days),
        notes=[
            f"short put {short.strike:.2f} (Δ {short.delta or 0:.3f})",
            f"long put {long.strike:.2f}",
            f"width {width:.2f}, credit {net_credit:.2f}",
        ],
    )


def bear_call_spread(
    underlying: str,
    spot: float,
    expiration: datetime,
    calls: list[OptionQuote],
    *,
    short_delta: float = 0.30,
    width_strikes: int = 1,
    quantity: int = 1,
) -> OptionStrategy | None:
    """Sell an OTM call spread (bearish / neutral income)."""
    ordered = _sort_calls(calls)
    short = _pick_by_delta(ordered, short_delta, sell=True)
    if short is None:
        return None
    short_idx = ordered.index(short)
    long_idx = short_idx + width_strikes
    if long_idx >= len(ordered):
        return None
    long = ordered[long_idx]

    short_mid = _mid(short) or 0.0
    long_mid = _mid(long) or 0.0
    net_credit = max(short_mid - long_mid, 0.0)
    width = long.strike - short.strike

    legs = [
        OptionLeg(
            contract=_contract(short, underlying, OptionType.CALL, expiration),
            side=OptionSide.SELL_TO_OPEN,
            quantity=quantity,
            theoretical=short_mid,
            delta=short.delta,
        ),
        OptionLeg(
            contract=_contract(long, underlying, OptionType.CALL, expiration),
            side=OptionSide.BUY_TO_OPEN,
            quantity=quantity,
            theoretical=long_mid,
            delta=long.delta,
        ),
    ]
    max_loss = width * 100.0 * quantity - net_credit * 100.0 * quantity
    max_profit = net_credit * 100.0 * quantity
    pop = 1.0 - (abs(short.delta) if short.delta is not None else short_delta)

    return OptionStrategy(
        strategy_id=f"bcs-{uuid.uuid4().hex[:12]}",
        name="bear_call_spread",
        underlying=underlying,
        legs=legs,
        net_credit=net_credit,
        max_loss=max_loss,
        max_profit=max_profit,
        break_even=[short.strike + net_credit],
        probability_of_profit=round(max(0.0, min(1.0, pop)), 4),
        days_to_expiration=max(0, (expiration - _now()).days),
        notes=[
            f"short call {short.strike:.2f} (Δ {short.delta or 0:.3f})",
            f"long call {long.strike:.2f}",
            f"width {width:.2f}, credit {net_credit:.2f}",
        ],
    )


def iron_condor(
    underlying: str,
    spot: float,
    expiration: datetime,
    calls: list[OptionQuote],
    puts: list[OptionQuote],
    *,
    short_delta: float = 0.20,
    width_strikes: int = 1,
    quantity: int = 1,
) -> OptionStrategy | None:
    """Neutral income: put credit spread + call credit spread."""
    put_side = bull_put_spread(
        underlying,
        spot,
        expiration,
        puts,
        short_delta=short_delta,
        width_strikes=width_strikes,
        quantity=quantity,
    )
    call_side = bear_call_spread(
        underlying,
        spot,
        expiration,
        calls,
        short_delta=short_delta,
        width_strikes=width_strikes,
        quantity=quantity,
    )
    if put_side is None or call_side is None:
        return None
    legs = put_side.legs + call_side.legs
    credit = (put_side.net_credit or 0.0) + (call_side.net_credit or 0.0)
    max_loss = (put_side.max_loss or 0.0) + (call_side.max_loss or 0.0)
    max_profit = (put_side.max_profit or 0.0) + (call_side.max_profit or 0.0)

    put_short = put_side.break_even[0] - (put_side.net_credit or 0.0)
    call_short = call_side.break_even[0] - (call_side.net_credit or 0.0)

    return OptionStrategy(
        strategy_id=f"ic-{uuid.uuid4().hex[:12]}",
        name="iron_condor",
        underlying=underlying,
        legs=legs,
        net_credit=credit,
        max_loss=max_loss,
        max_profit=max_profit,
        break_even=[put_short, call_short],
        probability_of_profit=round(
            (put_side.probability_of_profit or 0.5) * (call_side.probability_of_profit or 0.5), 4
        ),
        days_to_expiration=max(0, (expiration - _now()).days),
        notes=[
            f"put spread: {put_side.notes[0] if put_side.notes else ''}",
            f"call spread: {call_side.notes[0] if call_side.notes else ''}",
        ],
    )


def cash_secured_put(
    underlying: str,
    spot: float,
    expiration: datetime,
    puts: list[OptionQuote],
    *,
    short_delta: float = 0.30,
    quantity: int = 1,
    risk_free_rate: float = 0.04,
) -> OptionStrategy | None:
    """Sell a cash-secured put (defined max loss = strike×100 − premium)."""
    ordered = _sort_puts(puts)
    short = _pick_by_delta(ordered, short_delta, sell=True)
    if short is None:
        return None
    premium = _mid(short) or 0.0
    legs = [
        OptionLeg(
            contract=_contract(short, underlying, OptionType.PUT, expiration),
            side=OptionSide.SELL_TO_OPEN,
            quantity=quantity,
            theoretical=premium,
            delta=short.delta,
        )
    ]
    max_loss = short.strike * 100.0 * quantity - premium * 100.0 * quantity
    max_profit = premium * 100.0 * quantity
    pop = 1.0 - (short.delta if short.delta is not None else short_delta)

    return OptionStrategy(
        strategy_id=f"csp-{uuid.uuid4().hex[:12]}",
        name="cash_secured_put",
        underlying=underlying,
        legs=legs,
        net_credit=premium,
        max_loss=max_loss,
        max_profit=max_profit,
        break_even=[short.strike - premium],
        probability_of_profit=round(max(0.0, min(1.0, pop)), 4),
        days_to_expiration=max(0, (expiration - _now()).days),
        notes=[f"short put {short.strike:.2f} (Δ {short.delta or 0:.3f})"],
    )


def build_strategy(
    direction: DIRECTION,
    underlying: str,
    spot: float,
    expiration: datetime,
    calls: list[OptionQuote],
    puts: list[OptionQuote],
    *,
    short_delta: float = 0.30,
    width_strikes: int = 1,
    quantity: int = 1,
) -> OptionStrategy | None:
    """Dispatch to the deterministic strategy for a directional view."""
    if direction == "bullish":
        return bull_put_spread(
            underlying,
            spot,
            expiration,
            puts,
            short_delta=short_delta,
            width_strikes=width_strikes,
            quantity=quantity,
        )
    if direction == "bearish":
        return bear_call_spread(
            underlying,
            spot,
            expiration,
            calls,
            short_delta=short_delta,
            width_strikes=width_strikes,
            quantity=quantity,
        )
    return iron_condor(
        underlying,
        spot,
        expiration,
        calls,
        puts,
        short_delta=short_delta,
        width_strikes=width_strikes,
        quantity=quantity,
    )


def theoretical_price(leg: OptionLeg, spot: float, rate: float, vol: float) -> float:
    """Re-price a leg with BSM (used by the risk engine to sanity-check quotes)."""
    tte = max((leg.contract.expiration - _now()).total_seconds() / (365.0 * 86400.0), 1e-6)
    return black_scholes(spot, leg.contract.strike, tte, rate, vol, leg.contract.option_type)
