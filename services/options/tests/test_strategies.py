"""Unit tests for IV analytics and defined-risk strategy construction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from options.iv import iv_percentile, iv_rank
from options.schemas import OptionQuote
from options.strategies import bear_call_spread, build_strategy, bull_put_spread, iron_condor


def _q(symbol: str, strike: float, delta: float, bid: float, ask: float) -> OptionQuote:
    return OptionQuote(symbol=symbol, strike=strike, delta=delta, bid=bid, ask=ask)


def _expiry(days: int = 30) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


def _puts() -> list[OptionQuote]:
    return [
        _q("P95", 95.0, -0.05, 0.10, 0.15),
        _q("P97", 97.0, -0.15, 0.40, 0.50),
        _q("P100", 100.0, -0.30, 1.20, 1.30),
        _q("P102", 102.0, -0.45, 2.50, 2.60),
        _q("P105", 105.0, -0.60, 4.00, 4.10),
    ]


def _calls() -> list[OptionQuote]:
    return [
        _q("C100", 100.0, 0.30, 1.20, 1.30),
        _q("C102", 102.0, 0.15, 0.40, 0.50),
        _q("C105", 105.0, 0.05, 0.10, 0.15),
    ]


def test_iv_rank_midpoint() -> None:
    hist = [0.2, 0.25, 0.3, 0.35, 0.4]
    assert iv_rank(0.3, hist) == pytest.approx(0.5, abs=1e-9)


def test_iv_rank_needs_history() -> None:
    assert iv_rank(0.3, [0.3]) is None
    assert iv_rank(None, [0.2, 0.4]) is None


def test_iv_percentile() -> None:
    hist = [0.2, 0.25, 0.3, 0.35]
    assert iv_percentile(0.31, hist) == pytest.approx(0.75, abs=1e-9)


def test_bull_put_spread_defined_risk() -> None:
    s = bull_put_spread("AAPL", 100.0, _expiry(), _puts(), width_strikes=1)
    assert s is not None
    assert s.defined_risk
    assert s.max_loss is not None and s.max_loss > 0
    assert s.max_profit is not None and s.max_profit > 0
    assert len(s.legs) == 2
    # short put at 100, long put at 97 → width 3
    assert s.legs[0].contract.strike == 100.0
    assert s.legs[1].contract.strike == 97.0


def test_bull_put_spread_no_chain_returns_none() -> None:
    assert bull_put_spread("AAPL", 100.0, _expiry(), []) is None


def test_bear_call_spread_defined_risk() -> None:
    s = bear_call_spread("AAPL", 100.0, _expiry(), _calls(), width_strikes=1)
    assert s is not None
    assert s.defined_risk
    assert s.legs[0].contract.strike == 100.0
    assert s.legs[1].contract.strike == 102.0


def test_build_strategy_dispatch() -> None:
    assert build_strategy("bullish", "AAPL", 100.0, _expiry(), _calls(), _puts()) is not None
    assert build_strategy("bearish", "AAPL", 100.0, _expiry(), _calls(), _puts()) is not None
    assert build_strategy("neutral", "AAPL", 100.0, _expiry(), _calls(), _puts()) is not None


def test_iron_condor_four_legs() -> None:
    s = iron_condor("AAPL", 100.0, _expiry(), _calls(), _puts())
    assert s is not None
    assert len(s.legs) == 4
