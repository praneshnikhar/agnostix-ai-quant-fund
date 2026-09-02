"""M1 API + snapshot tests — deterministic; DB layer faked via monkeypatch."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

T0 = datetime.now(UTC) - timedelta(minutes=5)


class _Rec:
    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class FakeSession:
    async def commit(self) -> None:
        return None

    def add(self, obj) -> None:
        return None

    async def flush(self) -> None:
        return None


@pytest.fixture()
def seeded(monkeypatch):
    """Patch repositories used by the markets routes with in-memory fakes."""
    from app.api.routes import markets as m

    sec = _Rec(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        asset_class="us_equity",
        status="active",
        provider="alpaca_market_data",
        received_at=T0,
    )
    bar = _Rec(
        symbol="AAPL",
        timeframe="1Day",
        event_time=T0,
        open=100,
        high=110,
        low=99,
        close=105,
        volume=1000,
        trade_count=10,
        vwap=104,
        provider="alpaca_market_data",
        received_at=T0,
    )
    quote = _Rec(
        symbol="AAPL",
        event_time=T0,
        bid_price=99.9,
        bid_size=1,
        ask_price=100.1,
        ask_size=1,
        last_price=None,
        provider="alpaca_market_data",
        received_at=T0,
    )
    trade = _Rec(
        symbol="AAPL",
        event_time=T0,
        price=105,
        size=10,
        conditions=None,
        provider="alpaca_market_data",
        provider_trade_id="T1",
        received_at=T0,
    )
    news = _Rec(
        id=1,
        headline="h",
        summary=None,
        source="Reuters",
        url="https://x",
        symbols=["AAPL"],
        published_at=T0,
        received_at=T0,
        provider="alpaca_news",
        provider_article_id="n-1",
    )

    class R:
        def __init__(self, *a) -> None:
            pass

        async def get_by_symbol(self, symbol):
            return sec if symbol == "AAPL" else None

        async def get_all(self):
            return [sec]

    class B:
        def __init__(self, *a) -> None:
            pass

        async def get_bars(self, *a, **k):
            return [bar]

        async def get_latest_bar(self, symbol):
            return bar if symbol == "AAPL" else None

    class Q:
        def __init__(self, *a) -> None:
            pass

        async def get_latest_quote(self, symbol):
            return quote if symbol == "AAPL" else None

    class T:
        def __init__(self, *a) -> None:
            pass

        async def get_recent_trades(self, symbol, limit=50):
            return [trade] if symbol == "AAPL" else []

    class N:
        def __init__(self, *a) -> None:
            pass

        async def get_recent_news(self, symbols=None, limit=50, since=None):
            return [news]

    class S:
        async def save_snapshot(self, values):
            return values

    monkeypatch.setattr(m, "SecurityRepository", R)
    monkeypatch.setattr(m, "BarRepository", B)
    monkeypatch.setattr(m, "QuoteRepository", Q)
    monkeypatch.setattr(m, "TradeRepository", T)
    monkeypatch.setattr(m, "NewsRepository", N)
    monkeypatch.setattr(m, "SnapshotRepository", S)
    # snapshot service imports repositories from the repo module directly
    from app.db.repositories import market_data_repo as repo_mod

    monkeypatch.setattr(repo_mod, "SecurityRepository", R)
    monkeypatch.setattr(repo_mod, "BarRepository", B)
    monkeypatch.setattr(repo_mod, "QuoteRepository", Q)
    monkeypatch.setattr(repo_mod, "TradeRepository", T)
    monkeypatch.setattr(repo_mod, "NewsRepository", N)
    return m


@pytest.mark.anyio
async def test_list_markets(seeded) -> None:
    resp = await seeded.list_markets(FakeSession())
    assert resp.watchlist[0].symbol == "AAPL"


@pytest.mark.anyio
async def test_get_market_404(seeded) -> None:
    import fastapi

    with pytest.raises(fastapi.HTTPException) as ei:
        await seeded.get_market("ZZZZ", FakeSession())
    assert ei.value.status_code == 404


@pytest.mark.anyio
async def test_bars_quotes_trades_news(seeded) -> None:
    s = FakeSession()
    bars = await seeded.get_bars("aapl", session=s)
    assert bars["count"] == 1 and bars["bars"][0]["close"] == 105
    quotes = await seeded.get_quotes("AAPL", session=s)
    assert quotes["quote"]["bid_price"] == 99.9
    trades = await seeded.get_trades("AAPL", session=s)
    assert trades["trades"][0]["provider_trade_id"] == "T1"
    news = await seeded.get_news("AAPL", session=s)
    assert news["articles"][0]["headline"] == "h"


@pytest.mark.anyio
async def test_snapshot_shape_and_quality(seeded) -> None:
    from market_data.snapshot import build_snapshot

    snap = await build_snapshot(FakeSession(), "aapl")
    assert snap.symbol == "AAPL"
    assert snap.market["latest_bar"]["close"] == 105
    states = {d.datatype: d.state for d in snap.data_quality}
    assert states["bars"].value == "fresh"
    assert snap.fundamentals["status"] == "unavailable_in_m1"
    assert snap.macro["status"] == "unavailable_in_m1"


@pytest.mark.anyio
async def test_snapshot_missing_symbol_is_missing_state(monkeypatch) -> None:
    from market_data.snapshot import build_snapshot

    class Empty:
        def __init__(self, *a) -> None:
            pass

        async def get_by_symbol(self, symbol):
            return None

        async def get_latest_bar(self, symbol):
            return None

        async def get_latest_quote(self, symbol):
            return None

        async def get_recent_trades(self, symbol, limit=50):
            return []

        async def get_recent_news(self, symbols=None, limit=50, since=None):
            return []

    from app.db.repositories import market_data_repo as repo_mod

    for name in (
        "SecurityRepository",
        "BarRepository",
        "QuoteRepository",
        "TradeRepository",
        "NewsRepository",
    ):
        monkeypatch.setattr(repo_mod, name, Empty)
    snap = await build_snapshot(FakeSession(), "AAPL")
    assert all(d.state.value == "missing" for d in snap.data_quality)
    assert snap.market == {}


def test_no_order_endpoints() -> None:
    from app.main import create_app

    paths = list(create_app().openapi()["paths"].keys())
    market_paths = [p for p in paths if p.startswith("/markets")]
    assert market_paths
    for p in market_paths:
        assert "order" not in p.lower()
