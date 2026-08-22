"""Worker ingestion tests — pure helpers with fakes; no broker/DB/Redis."""

from __future__ import annotations

from datetime import UTC, datetime

from app.workers.tasks_ingestion import (
    _is_transient,
    load_watchlist,
    run_ingestion_bars,
    run_ingestion_news,
    run_ingestion_quotes,
    run_ingestion_security_metadata,
    run_ingestion_trades,
)
from market_data.providers.base import ProviderError
from market_data.schemas import Bar, NewsArticle, ProviderInfo, Quote, Security, Trade

T0 = datetime(2024, 6, 3, 14, 30, tzinfo=UTC)
PROV = ProviderInfo(provider="test")


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_bars(self, symbol, timeframe="1Day", start=None, end=None, limit=500):
        self.calls.append("bars")
        good = Bar(symbol=symbol, event_time=T0, open=100, high=110, low=99,
                   close=105, volume=1000, provider_info=PROV, received_at=T0)
        bad = Bar.model_construct(symbol=symbol, event_time=T0, open=100, high=90,
                                  low=99, close=105, volume=1000,
                                  provider_info=PROV, received_at=T0)
        return [good, bad]

    def get_latest_quote(self, symbol):
        self.calls.append("quote")
        return Quote(symbol=symbol, event_time=T0, bid_price=99.9, ask_price=100.1,
                     provider_info=PROV, received_at=T0)

    def get_recent_trades(self, symbol, limit=50):
        self.calls.append("trades")
        return [Trade(symbol=symbol, event_time=T0, price=105, size=10,
                      provider_info=PROV, received_at=T0)]

    def get_security(self, symbol):
        self.calls.append("security")
        return Security(symbol=symbol, name="Test Co", exchange="NASDAQ",
                        provider_info=PROV, received_at=T0)


class FakeNewsProvider:
    def __init__(self, articles=None) -> None:
        self.articles = articles if articles is not None else [
            NewsArticle(provider_article_id="1", headline="h", url="https://x",
                        symbols=["AAPL"], published_at=T0,
                        provider_info=PROV, received_at=T0),
            NewsArticle(provider_article_id="2", headline="bad", url="ftp://x",
                        published_at=T0, provider_info=PROV, received_at=T0),
        ]

    def get_news(self, symbols=None, limit=50):
        return self.articles


class FakeRepoFactory:
    """Records rows written; simulates dedupe on second identical write."""

    def __init__(self) -> None:
        self.written: list[dict] = []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    # repository-compatible methods used via getattr in helpers? No — helpers
    # import real repositories. Instead we patch at module level in tests.
    async def upsert_bars(self, rows):
        new = [r for r in rows if r not in self.written]
        self.written.extend(new)
        return len(new)


def test_load_watchlist_default_and_env(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_WATCHLIST", raising=False)
    assert load_watchlist()[0] == "AAPL"
    monkeypatch.setenv("MARKET_WATCHLIST", " aapl , msft ")
    assert load_watchlist() == ["AAPL", "MSFT"]


def test_run_ingestion_bars_counts_and_persists(monkeypatch) -> None:
    fake_repo = FakeRepoFactory()
    monkeypatch.setattr(
        "app.db.repositories.market_data_repo.BarRepository.upsert_bars",
        lambda self, rows: fake_repo.upsert_bars(rows),
    )
    summary = run_ingestion_bars("AAPL", provider=FakeProvider(), repo_factory=fake_repo)
    assert summary["fetched"] == 2
    assert summary["valid"] == 1
    assert summary["invalid"] == 1
    assert summary["persisted"] == 1


def test_run_ingestion_quotes(monkeypatch) -> None:
    wrote = []

    async def fake_insert(self, rows):
        wrote.extend(rows)
        return len(rows)

    monkeypatch.setattr(
        "app.db.repositories.market_data_repo.QuoteRepository.insert_quotes", fake_insert
    )
    summary = run_ingestion_quotes("AAPL", provider=FakeProvider(), repo_factory=FakeRepoFactory)
    assert summary["persisted"] == 1
    assert wrote and wrote[0]["symbol"] == "AAPL"


def test_run_ingestion_trades(monkeypatch) -> None:
    wrote = []

    async def fake_insert(self, rows):
        wrote.extend(rows)
        return len(rows)

    monkeypatch.setattr(
        "app.db.repositories.market_data_repo.TradeRepository.insert_trades", fake_insert
    )
    summary = run_ingestion_trades("AAPL", provider=FakeProvider(), repo_factory=FakeRepoFactory)
    assert summary["valid"] == 1
    assert summary["persisted"] == 1


def test_run_ingestion_news_drops_invalid(monkeypatch) -> None:
    wrote = []

    async def fake_upsert(self, rows):
        wrote.extend(rows)
        return len(rows)

    monkeypatch.setattr(
        "app.db.repositories.market_data_repo.NewsRepository.upsert_news", fake_upsert
    )
    summary = run_ingestion_news(provider=FakeNewsProvider(), repo_factory=FakeRepoFactory)
    assert summary["fetched"] == 2
    assert summary["invalid"] == 1
    assert summary["persisted"] == 1


def test_run_ingestion_duplicate_handling(monkeypatch) -> None:
    fake_repo = FakeRepoFactory()
    monkeypatch.setattr(
        "app.db.repositories.market_data_repo.BarRepository.upsert_bars",
        lambda self, rows: fake_repo.upsert_bars(rows),
    )
    first = run_ingestion_bars("AAPL", provider=FakeProvider(), repo_factory=fake_repo)
    second = run_ingestion_bars("AAPL", provider=FakeProvider(), repo_factory=fake_repo)
    assert first["persisted"] == 1
    assert second["persisted"] == 0  # duplicate suppressed


def test_run_ingestion_security_metadata(monkeypatch) -> None:
    called = {}

    async def fake_upsert(self, values):
        called.update(values)

    monkeypatch.setattr(
        "app.db.repositories.market_data_repo.SecurityRepository.upsert_security", fake_upsert
    )
    summary = run_ingestion_security_metadata(
        "AAPL", provider=FakeProvider(), repo_factory=FakeRepoFactory
    )
    assert summary["persisted"] == 1
    assert called["name"] == "Test Co"


def test_transient_classification() -> None:
    assert _is_transient(ProviderError("connection timeout"))
    assert _is_transient(ProviderError("HTTP 503"))
    assert not _is_transient(ProviderError("auth failed"))
    assert not _is_transient(ValueError("nope"))


def test_celery_tasks_have_retry_config() -> None:
    from app.workers.tasks_ingestion import ingest_bars

    assert ingest_bars.max_retries == 3
    assert ingest_bars.retry_backoff is True
    assert ingest_bars.retry_backoff_max == 600


def test_beat_schedule_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_INGESTION_SCHEDULE_ENABLED", raising=False)
    from app.workers.celery_app import celery_app

    assert celery_app.conf.beat_schedule == {}
