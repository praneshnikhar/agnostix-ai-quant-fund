"""Schema contract tests: tz-awareness, symbol normalization, snapshot state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from market_data.schemas import (
    Bar,
    FreshnessState,
    MarketDataStatus,
    MarketSnapshot,
    NewsArticle,
    ProviderInfo,
)

T0 = datetime(2024, 6, 3, 14, 30, tzinfo=UTC)
RECV = datetime(2024, 6, 3, 14, 30, 1, tzinfo=UTC)


def _bar(**overrides: Any) -> Bar:
    base: dict[str, Any] = dict(
        symbol="aapl",
        event_time=T0,
        open=100.0,
        high=110.0,
        low=99.0,
        close=105.0,
        volume=1_000_000.0,
        provider_info=ProviderInfo(provider="alpaca_market_data"),
        received_at=RECV,
    )
    base.update(overrides)
    return Bar(**base)


def test_bar_symbol_uppercased() -> None:
    assert _bar().symbol == "AAPL"


def test_naive_event_time_rejected() -> None:
    with pytest.raises(ValidationError):
        _bar(event_time=datetime(2024, 6, 3, 14, 30))


def test_naive_received_at_rejected() -> None:
    with pytest.raises(ValidationError):
        _bar(received_at=datetime(2024, 6, 3, 14, 30))


def test_nonpositive_price_rejected() -> None:
    with pytest.raises(ValidationError):
        _bar(close=0)


def test_negative_volume_rejected() -> None:
    with pytest.raises(ValidationError):
        _bar(volume=-1)


def test_news_symbols_uppercased() -> None:
    article = NewsArticle(
        provider_article_id="n1",
        headline="Test headline",
        symbols=["aapl", "msft"],
        published_at=T0,
        provider_info=ProviderInfo(provider="alpaca_news"),
        received_at=RECV,
    )
    assert article.symbols == ["AAPL", "MSFT"]


def test_news_empty_headline_rejected() -> None:
    with pytest.raises(ValidationError):
        NewsArticle(
            provider_article_id="n1",
            headline="",
            published_at=T0,
            provider_info=ProviderInfo(provider="alpaca_news"),
            received_at=RECV,
        )


def test_snapshot_overall_state_worst_wins() -> None:
    def status(state: FreshnessState) -> MarketDataStatus:
        return MarketDataStatus(datatype="bars", symbol="AAPL", state=state)

    snap = MarketSnapshot(
        symbol="AAPL",
        generated_at=T0,
        data_quality=[status(FreshnessState.FRESH), status(FreshnessState.STALE)],
    )
    assert snap.overall_state == FreshnessState.STALE

    snap2 = MarketSnapshot(
        symbol="AAPL",
        generated_at=T0,
        data_quality=[status(FreshnessState.STALE), status(FreshnessState.MISSING)],
    )
    assert snap2.overall_state == FreshnessState.MISSING


def test_snapshot_severity_ordering_missing_worst_then_invalid() -> None:
    def status(state: FreshnessState) -> MarketDataStatus:
        return MarketDataStatus(datatype="bars", symbol="AAPL", state=state)

    snap = MarketSnapshot(
        symbol="AAPL",
        generated_at=T0,
        data_quality=[status(FreshnessState.INVALID), status(FreshnessState.STALE)],
    )
    assert snap.overall_state == FreshnessState.INVALID


def test_snapshot_fundamentals_marked_unavailable() -> None:
    snap = MarketSnapshot(symbol="AAPL", generated_at=T0)
    assert snap.fundamentals["status"] == "unavailable_in_m1"
    assert snap.macro["status"] == "unavailable_in_m1"


def test_snapshot_no_data_quality_defaults_fresh() -> None:
    snap = MarketSnapshot(symbol="AAPL", generated_at=T0)
    assert snap.overall_state == FreshnessState.FRESH
