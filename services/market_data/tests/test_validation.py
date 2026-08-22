"""Validation rule tests and batch splitting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from market_data.schemas import Bar, NewsArticle, ProviderInfo, Quote, Trade
from market_data.validation import (
    validate_bar,
    validate_batch,
    validate_news,
    validate_quote,
    validate_trade,
)

T0 = datetime(2024, 6, 3, 14, 30, tzinfo=UTC)
RECV = T0 + timedelta(seconds=1)
PROV = ProviderInfo(provider="test")


def _bar(**kw: object) -> Bar:
    base: dict[str, object] = dict(
        symbol="AAPL",
        event_time=T0,
        open=100.0,
        high=110.0,
        low=99.0,
        close=105.0,
        volume=1000.0,
        provider_info=PROV,
        received_at=RECV,
    )
    base.update(kw)
    return Bar(**base)  # type: ignore[arg-type]


def test_valid_bar_has_no_problems() -> None:
    assert validate_bar(_bar()) == []


def test_bar_ohlc_violations() -> None:
    problems = validate_bar(_bar(high=90.0))
    assert any("high < low" in p for p in problems)
    assert any("max(open" in p for p in problems)


def test_bar_future_event_time_flagged() -> None:
    future = datetime.now(UTC) + timedelta(hours=2)
    problems = validate_bar(_bar(event_time=future))
    assert any("future" in p for p in problems)


def test_quote_crossed_book() -> None:
    q = Quote(
        symbol="AAPL",
        event_time=T0,
        bid_price=101.0,
        ask_price=100.0,
        provider_info=PROV,
        received_at=RECV,
    )
    assert any("crossed" in p for p in validate_quote(q))


def test_trade_nonpositive() -> None:
    # model_construct bypasses pydantic field constraints so the explicit
    # validator rules can be exercised independently.
    t = Trade.model_construct(
        symbol="AAPL", event_time=T0, price=-1.0, size=10.0, provider_info=PROV, received_at=RECV
    )
    assert any("price" in p for p in validate_trade(t))


def test_news_bad_url_scheme() -> None:
    n = NewsArticle(
        provider_article_id="1",
        headline="h",
        url="ftp://x",
        published_at=T0,
        provider_info=PROV,
        received_at=RECV,
    )
    assert any("http" in p for p in validate_news(n))


def test_validate_batch_splits() -> None:
    good = _bar()
    bad = _bar(high=50.0)  # high < low
    valid, invalid = validate_batch([good, bad], validate_bar)
    assert len(valid) == 1
    assert len(invalid) == 1
    idx, problems = invalid[0]
    assert idx == 1
    assert problems
