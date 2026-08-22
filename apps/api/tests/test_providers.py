"""Provider tests — deterministic fakes, no live Alpaca API."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from market_data.providers.alpaca_market_data import AlpacaMarketDataProvider
from market_data.providers.alpaca_news import AlpacaNewsProvider
from market_data.providers.base import ProviderError
from market_data.schemas import Bar, NewsArticle, Quote, Trade


class FakeSDK:
    """Mimics the alpaca-py client surface used by providers."""

    def get_stock_bars(self, request) -> dict:
        return {
            "AAPL": [
                {
                    "S": "AAPL",
                    "t": "2024-06-03T14:30:00Z",
                    "o": 100.0,
                    "h": 110.0,
                    "l": 99.0,
                    "c": 105.0,
                    "v": 1000,
                    "n": 10,
                    "vw": 104.0,
                },
                # un-normalizable timestamp -> dropped by provider
                {
                    "S": "AAPL",
                    "t": "not-a-time",
                    "o": 100.0,
                    "h": 110.0,
                    "l": 99.0,
                    "c": 105.0,
                    "v": 1000,
                },
            ]
        }

    def get_stock_latest_quote(self, params) -> dict:
        return {
            "AAPL": [
                {
                    "S": "AAPL",
                    "t": "2024-06-03T14:30:00Z",
                    "ap": 120.1,
                    "as": 300,
                    "bp": 119.9,
                    "bs": 200,
                }
            ]
        }

    def get_stock_trades(self, request) -> dict:
        return {
            "AAPL": [{"S": "AAPL", "t": "2024-06-03T14:30:00Z", "p": 105.0, "s": 10, "i": "T1"}]
        }

    def get_asset(self, symbol):
        class A:
            def __init__(self, sym: str) -> None:
                self.symbol = sym
                self.name = "Apple Inc."
                self.exchange = "NASDAQ"
                self.status = "active"
                self.asset_class = "us_equity"

        return A(symbol)

    def get_news(self, params):
        class N:
            def __init__(self) -> None:
                self.id = 1
                self.headline = "Chip demand surges"
                self.summary = "Long summary"
                self.source = "Reuters"
                self.url = "https://example.com/a"
                self.symbols = ["NVDA"]
                self.created_at = datetime(2024, 6, 3, 13, 0, tzinfo=UTC)

        class Resp:
            def __init__(self) -> None:
                self.news = [N()]

        return Resp()


class FailingSDK:
    def get_stock_bars(self, request):
        raise RuntimeError("connection timeout")


def test_get_bars_normalizes_and_drops_invalid() -> None:
    p = AlpacaMarketDataProvider(client=FakeSDK())
    bars = p.get_bars("aapl")
    assert len(bars) == 1
    bar = bars[0]
    assert isinstance(bar, Bar)
    assert bar.symbol == "AAPL"
    assert bar.close == 105.0
    assert bar.provider_info.provider == "alpaca_market_data"


def test_get_bars_wraps_sdk_errors() -> None:
    p = AlpacaMarketDataProvider(client=FailingSDK())
    with pytest.raises(ProviderError):
        p.get_bars("AAPL")


def test_get_latest_quote_internal_schema() -> None:
    p = AlpacaMarketDataProvider(client=FakeSDK())
    q = p.get_latest_quote("AAPL")
    assert isinstance(q, Quote)
    assert q.bid_price == 119.9
    assert q.ask_price == 120.1


def test_get_recent_trades_internal_schema() -> None:
    p = AlpacaMarketDataProvider(client=FakeSDK())
    trades = p.get_recent_trades("AAPL")
    assert len(trades) == 1
    t = trades[0]
    assert isinstance(t, Trade)
    assert t.provider_trade_id == "T1"


def test_get_security_internal_schema() -> None:
    p = AlpacaMarketDataProvider(client=FakeSDK())
    s = p.get_security("AAPL")
    assert s is not None
    assert s.name == "Apple Inc."
    assert s.exchange == "NASDAQ"


def test_news_provider_internal_schema() -> None:
    p = AlpacaNewsProvider(client=FakeSDK())
    articles = p.get_news(symbols=["nvda"])
    assert len(articles) == 1
    a = articles[0]
    assert isinstance(a, NewsArticle)
    assert a.symbols == ["NVDA"]
    assert a.provider_info.provider == "alpaca_news"


def test_no_order_methods_on_providers() -> None:
    for cls in (AlpacaMarketDataProvider, AlpacaNewsProvider):
        for name in dir(cls):
            assert "order" not in name.lower()
            assert "submit" not in name.lower()


def test_default_client_requires_credentials(monkeypatch) -> None:
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET_KEY", raising=False)
    with pytest.raises(ProviderError):
        AlpacaMarketDataProvider._build_default_client()
