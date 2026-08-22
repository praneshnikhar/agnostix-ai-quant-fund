"""Normalization tests: Alpaca-style keys, timestamp formats, error paths."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from market_data.normalization import (
    NormalizationError,
    normalize_bar,
    normalize_news,
    normalize_quote,
    normalize_security,
    normalize_trade,
    parse_timestamp,
)

RECV = datetime(2024, 6, 3, 14, 30, 1, tzinfo=UTC)


def test_normalize_bar_alpaca_short_keys() -> None:
    bar = normalize_bar(
        {
            "S": "aapl",
            "t": "2024-06-03T14:30:00Z",
            "o": "100.0",
            "h": 110.0,
            "l": 99.0,
            "c": 105.5,
            "v": 1_000_000,
            "n": 500,
            "vw": 104.2,
        },
        provider="alpaca_market_data",
        received_at=RECV,
    )
    assert bar.symbol == "AAPL"
    assert bar.event_time == datetime(2024, 6, 3, 14, 30, tzinfo=UTC)
    assert bar.open == 100.0
    assert bar.close == 105.5
    assert bar.trade_count == 500
    assert bar.vwap == 104.2
    assert bar.provider_info.provider == "alpaca_market_data"
    assert bar.received_at == RECV
    assert bar.stored_at is None


def test_normalize_bar_verbose_keys() -> None:
    bar = normalize_bar(
        {
            "symbol": "MSFT",
            "timestamp": "2024-06-03T20:00:00+00:00",
            "open": 400.0,
            "high": 410.0,
            "low": 395.0,
            "close": 405.0,
            "volume": 2_000_000,
        },
        provider="test",
        received_at=RECV,
    )
    assert bar.symbol == "MSFT"
    assert bar.high == 410.0


def test_normalize_bar_missing_field_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_bar({"S": "AAPL", "t": "2024-06-03T14:30:00Z"}, provider="x", received_at=RECV)


def test_normalize_bar_garbage_number_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_bar(
            {"S": "AAPL", "t": "2024-06-03T14:30:00Z", "o": "abc", "h": 1, "l": 1, "c": 1, "v": 1},
            provider="x",
            received_at=RECV,
        )


def test_normalize_bar_naive_timestamp_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_bar(
            {"S": "AAPL", "t": "2024-06-03T14:30:00", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1},
            provider="x",
            received_at=RECV,
        )


def test_normalize_quote() -> None:
    q = normalize_quote(
        {"S": "NVDA", "t": 1717425000000000000, "ap": 120.1, "as": 300, "bp": 119.9, "bs": 200},
        provider="alpaca_market_data",
        received_at=RECV,
    )
    assert q.symbol == "NVDA"
    assert q.bid_price == 119.9
    assert q.ask_price == 120.1


def test_normalize_trade() -> None:
    t = normalize_trade(
        {"S": "AMD", "t": "2024-06-03T14:30:00.500Z", "p": 160.25, "s": 100, "i": "T123"},
        provider="alpaca_market_data",
        received_at=RECV,
    )
    assert t.price == 160.25
    assert t.size == 100
    assert t.provider_trade_id == "T123"


def test_normalize_news() -> None:
    n = normalize_news(
        {
            "id": 42,
            "headline": "Chip demand surges",
            "summary": "Long summary",
            "source": "Reuters",
            "url": "https://example.com/a",
            "symbols": ["nvda"],
            "created_at": "2024-06-03T13:00:00Z",
        },
        provider="alpaca_news",
        received_at=RECV,
    )
    assert n.provider_article_id == "42"
    assert n.symbols == ["NVDA"]
    assert n.published_at.hour == 13


def test_normalize_security() -> None:
    s = normalize_security(
        {"symbol": "tsla", "name": "Tesla, Inc.", "exchange": "NASDAQ", "status": "active"},
        provider="alpaca_market_data",
        received_at=RECV,
    )
    assert s.symbol == "TSLA"
    assert s.exchange == "NASDAQ"


def test_normalize_security_bad_status_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_security({"symbol": "X", "status": "weird"}, provider="x", received_at=RECV)


def test_parse_timestamp_epoch_seconds_and_millis() -> None:
    base = datetime(2024, 6, 3, 14, 30, tzinfo=UTC)
    assert parse_timestamp(1717425000) == base
    assert parse_timestamp(1717425000000) == base
    assert parse_timestamp(1717425000000000000) == base
    assert parse_timestamp("2024-06-03T14:30:00Z") == base


def test_parse_timestamp_unparseable_raises() -> None:
    with pytest.raises(NormalizationError):
        parse_timestamp("not-a-time")
