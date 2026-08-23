"""M1→M2 research-context projection tests (deterministic, pure).

Covers snapshot_research_summary + context_news_items: determinism,
boundedness, JSON-stable value coercion, and verbatim freshness states
(staleness is never hidden or upgraded). No live providers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from market_data.schemas import (
    FreshnessState,
    MarketDataStatus,
    MarketSnapshot,
    NewsArticle,
    ProviderInfo,
)
from market_data.snapshot import context_news_items, snapshot_research_summary

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
NEWS_PROV = ProviderInfo(provider="alpaca_news", raw_record_id="raw-1")


def _article(i: int, published: datetime) -> NewsArticle:
    return NewsArticle(
        provider_article_id=f"a-{i}",
        headline=f"Headline {i}",
        summary=f"Summary {i}" if i % 2 == 0 else None,
        source="Reuters" if i % 2 == 0 else "Bloomberg",
        url=f"https://example.com/{i}",
        symbols=["ACME"],
        published_at=published,
        provider_info=NEWS_PROV,
        received_at=published + timedelta(minutes=1),
    )


def _status(
    datatype: str, state: FreshnessState, as_of: datetime | None = None
) -> MarketDataStatus:
    return MarketDataStatus(
        datatype=datatype,
        symbol="ACME",
        state=state,
        as_of=as_of,
        threshold_seconds=3600.0,
    )


def test_summary_projection_deterministic_and_json_stable():
    snap = MarketSnapshot(
        symbol="ACME",
        generated_at=NOW,
        market={
            "latest_bar": {
                "event_time": NOW - timedelta(hours=1),
                "close": Decimal("91.20"),
                "provider": "alpaca_market_data",
                "received_at": NOW - timedelta(hours=1),
            },
            "recent_trades": [{"price": 1}, {"price": 2}, {"price": 3}],
        },
        data_quality=[_status("bars", FreshnessState.FRESH, NOW - timedelta(hours=1))],
    )
    s1 = snapshot_research_summary(snap)
    s2 = snapshot_research_summary(snap)
    assert s1 == s2
    # JSON-stable coercions for hashing/rendering.
    assert isinstance(s1["market"]["latest_bar"]["close"], float)
    assert isinstance(s1["market"]["latest_bar"]["event_time"], str)
    assert s1["market"]["latest_bar"]["event_time"].endswith("+00:00")
    # Bounded: trade prints collapse to a count.
    assert s1["market"]["recent_trades_count"] == 3
    assert "recent_trades" not in s1["market"]
    # Wall-clock-volatile fields are excluded (determinism across builds).
    assert "generated_at" not in s1
    assert all("age_seconds" not in d for d in s1["data_quality"])
    # Discrete freshness state retained verbatim.
    assert s1["overall_state"] == "fresh"
    assert s1["data_quality"][0]["state"] == "fresh"


def test_stale_state_preserved_not_upgraded():
    snap = MarketSnapshot(
        symbol="ACME",
        generated_at=NOW,
        data_quality=[_status("bars", FreshnessState.STALE, NOW - timedelta(days=3))],
    )
    s = snapshot_research_summary(snap)
    assert s["overall_state"] == "stale"
    assert s["data_quality"][0]["state"] == "stale"


def test_overall_state_is_worst_datatype():
    snap = MarketSnapshot(
        symbol="ACME",
        generated_at=NOW,
        data_quality=[
            _status("bars", FreshnessState.FRESH, NOW - timedelta(hours=1)),
            _status("quotes", FreshnessState.MISSING),
        ],
    )
    assert snapshot_research_summary(snap)["overall_state"] == "missing"


def test_news_projection_preserves_full_provenance():
    arts = [_article(1, NOW - timedelta(hours=2))]
    items = context_news_items(arts)
    item = items[0]
    assert item["provider_article_id"] == "a-1"
    assert item["provider"] == "alpaca_news"
    assert item["headline"] == "Headline 1"
    assert item["source"] == "Bloomberg"
    assert item["url"] == "https://example.com/1"
    assert item["symbols"] == ["ACME"]
    assert item["published_at"] == arts[0].published_at
    assert item["received_at"] == arts[0].received_at
    assert item["summary"] is None


def test_news_projection_deterministic_and_non_mutating():
    arts = [_article(1, NOW - timedelta(hours=2)), _article(2, NOW - timedelta(hours=1))]
    first = context_news_items(arts)
    second = context_news_items(list(reversed(arts)))
    assert [i["provider_article_id"] for i in first] == ["a-1", "a-2"]
    assert [i["provider_article_id"] for i in second] == ["a-2", "a-1"]
    # Input objects untouched.
    assert arts[0].symbols == ["ACME"]
