"""M2.1 research-context integration tests.

Verifies that M1 NewsArticle + MarketSnapshot data flow into the
FundamentalResearchContext deterministically, with explicit freshness /
gap semantics and stable hashing. Pure functions + fixtures only — no
live providers, no LLM calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fundamentals.context import (
    CONTEXT_VERSION,
    MAX_NEWS,
    ContextNewsItem,
    build_fundamental_context,
    render_context_for_model,
)
from fundamentals.research.grounding import check_evidence_existence
from fundamentals.research.schemas import (
    Assessment,
    ClaimCheckStatus,
    EvidenceRef,
    FundamentalView,
    InvestmentThesis,
)
from market_data.freshness import evaluate_freshness, load_thresholds_from_settings
from market_data.schemas import MarketSnapshot, NewsArticle, ProviderInfo
from market_data.snapshot import context_news_items, snapshot_research_summary

NOW = datetime(2026, 8, 1, tzinfo=UTC)
NEWS_PROV = ProviderInfo(provider="alpaca_news", raw_record_id="raw-1")


# ------------------------------------------------------------------ helpers


def _article(i: int, published: datetime, headline: str | None = None) -> NewsArticle:
    return NewsArticle(
        provider_article_id=f"a-{i}",
        headline=headline or f"Headline {i}",
        summary=None,
        source="Reuters",
        url=f"https://example.com/{i}",
        symbols=["ACME"],
        published_at=published,
        provider_info=NEWS_PROV,
        received_at=published + timedelta(minutes=1),
    )


def _freshness(datatype: str, event_time: datetime | None):
    """Real M1 freshness evaluation against the fixed NOW instant."""
    thresholds = load_thresholds_from_settings(None)
    _, status = evaluate_freshness(
        event_time, NOW, thresholds.for_datatype(datatype), symbol="ACME", datatype=datatype
    )
    return status


def _snapshot(*, articles: list[NewsArticle] | None = None, bar_age: timedelta | None = None):
    """MarketSnapshot assembled exactly as build_snapshot would produce it."""
    arts = articles if articles is not None else []
    newest_news = max((a.published_at for a in arts), default=None)
    bar_time = NOW - bar_age if bar_age is not None else None
    market: dict = {}
    if bar_time is not None:
        market["latest_bar"] = {
            "event_time": bar_time,
            "close": 91.20,
            "provider": "alpaca_market_data",
            "received_at": bar_time,
        }
    return MarketSnapshot(
        symbol="ACME",
        generated_at=NOW,
        market=market,
        news=arts,
        data_quality=[
            _freshness("bars", bar_time),
            _freshness("news", newest_news),
        ],
    )


def _news_state(snapshot: MarketSnapshot) -> str:
    return next(d.state.value for d in snapshot.data_quality if d.datatype == "news")


def _ctx(snapshot: MarketSnapshot | None = None):
    """Context built through the exact projections the research service uses."""
    if snapshot is None:
        snapshot = _snapshot(
            articles=[_article(1, NOW - timedelta(hours=1))],
            bar_age=timedelta(hours=1),
        )
    return build_fundamental_context(
        "ACME",
        profile=None,
        metrics=[],
        documents=[],
        news=[ContextNewsItem.model_validate(d) for d in context_news_items(snapshot.news)],
        news_freshness=_news_state(snapshot),
        market_snapshot_summary=snapshot_research_summary(snapshot),
        market_snapshot_generated_at=snapshot.generated_at,
        now=NOW,
    )


def _thesis(source: str) -> InvestmentThesis:
    return InvestmentThesis(
        symbol="ACME",
        research_timestamp=NOW,
        fundamental_view=FundamentalView.NEUTRAL,
        confidence=0.5,
        investment_thesis="Neutral pending more data.",
        financial_assessment=Assessment(area="financial", summary="ok"),
        growth_assessment=Assessment(area="growth", summary="ok"),
        profitability_assessment=Assessment(area="profitability", summary="ok"),
        cash_flow_assessment=Assessment(area="cash_flow", summary="ok"),
        balance_sheet_assessment=Assessment(area="balance_sheet", summary="ok"),
        valuation_assessment=Assessment(area="valuation", summary="ok"),
        evidence=[
            EvidenceRef(
                evidence_id="ev-news-1",
                source=source,
                source_type="news",
                claim_supported="context",
            )
        ],
    )


# ------------------------------------------------------------- requirements


def test_context_version_bumped_for_material_schema_change():
    assert CONTEXT_VERSION == "m2-v2"


def test_context_contains_market_snapshot():
    ctx = _ctx()
    assert ctx.market_snapshot_summary["symbol"] == "ACME"
    assert ctx.market_snapshot_summary["overall_state"] == "fresh"
    assert ctx.market_snapshot_generated_at == NOW
    states = {s.datatype: s.state.value for s in ctx.data_status}
    assert states["market_snapshot"] == "ok"


def test_context_contains_news_with_full_provenance():
    ctx = _ctx()
    assert len(ctx.news) == 1
    n = ctx.news[0]
    assert isinstance(n, ContextNewsItem)
    assert n.provider_article_id == "a-1"
    assert n.provider == "alpaca_news"
    assert n.source == "Reuters"
    assert n.url == "https://example.com/1"
    assert n.published_at == NOW - timedelta(hours=1)
    assert n.received_at == NOW - timedelta(hours=1) + timedelta(minutes=1)
    assert n.symbols == ["ACME"]
    assert ctx.unavailable and "news" not in ctx.unavailable


def test_news_ordering_deterministic_newest_first_with_stable_ties():
    arts = [
        _article(3, NOW - timedelta(hours=3)),
        _article(1, NOW - timedelta(hours=1)),
        # Equal timestamps: tie-break must be provider_article_id ascending.
        _article(22, NOW - timedelta(hours=2)),
        _article(5, NOW - timedelta(hours=2)),
    ]
    ctx_a = _ctx(_snapshot(articles=arts))
    ctx_b = _ctx(_snapshot(articles=list(reversed(arts))))
    ids_a = [n.provider_article_id for n in ctx_a.news]
    ids_b = [n.provider_article_id for n in ctx_b.news]
    assert ids_a == ids_b  # input order irrelevant
    # Newest first; among equal timestamps the earlier id wins (stable sort).
    assert ids_a == ["a-1", "a-22", "a-5", "a-3"]


def test_news_budget_truncates_to_max_news():
    arts = [_article(i, NOW - timedelta(hours=i)) for i in range(8)]
    ctx = _ctx(_snapshot(articles=arts))
    assert len(ctx.news) == MAX_NEWS == 5
    # The five NEWEST articles survive truncation.
    assert [n.provider_article_id for n in ctx.news] == [f"a-{i}" for i in range(5)]


def test_news_dedupe_by_provider_identity():
    dup = _article(1, NOW - timedelta(hours=1))
    ctx = _ctx(_snapshot(articles=[dup, _article(2, NOW - timedelta(hours=2)), dup]))
    ids = [(n.provider, n.provider_article_id) for n in ctx.news]
    assert len(ids) == len(set(ids)) == 2


def test_missing_market_snapshot_is_explicit_gap():
    ctx = build_fundamental_context("ACME", profile=None, metrics=[], now=NOW)
    assert "market_snapshot" in ctx.unavailable
    entry = next(s for s in ctx.data_status if s.datatype == "market_snapshot")
    assert entry.state.value == "unavailable"
    text = render_context_for_model(ctx)
    assert "MARKET SNAPSHOT" in text
    assert "unavailable" in text


def test_missing_news_is_explicit_gap():
    ctx = _ctx(_snapshot(articles=[], bar_age=timedelta(hours=1)))
    assert "news" in ctx.unavailable
    entry = next(s for s in ctx.data_status if s.datatype == "news")
    assert entry.state.value == "unavailable"
    text = render_context_for_model(ctx)
    assert "RECENT NEWS" in text
    assert "unavailable" in text


def test_stale_snapshot_not_fresh_and_not_missing():
    ctx = _ctx(
        _snapshot(
            articles=[_article(1, NOW - timedelta(hours=1))],
            bar_age=timedelta(days=3),  # bars threshold is 24h -> stale
        )
    )
    summary = ctx.market_snapshot_summary
    assert summary["overall_state"] == "stale"
    bars = next(d for d in summary["data_quality"] if d["datatype"] == "bars")
    assert bars["state"] == "stale"  # never upgraded to fresh
    entry = next(s for s in ctx.data_status if s.datatype == "market_snapshot")
    assert entry.state.value == "incomplete"  # present-but-stale, not OK
    assert "market_snapshot" not in ctx.unavailable  # stale != missing
    assert "stale" in render_context_for_model(ctx)


def test_stale_news_not_fresh_and_not_missing():
    ctx = _ctx(
        _snapshot(
            articles=[_article(1, NOW - timedelta(hours=48))],  # news threshold is 6h
            bar_age=timedelta(hours=1),
        )
    )
    entry = next(s for s in ctx.data_status if s.datatype == "news")
    assert entry.state.value == "incomplete"
    assert "stale" in (entry.detail or "")
    assert "news" not in ctx.unavailable  # stale != missing
    rendered = render_context_for_model(ctx)
    assert "feed freshness=stale" in rendered


def test_invalid_news_state_maps_to_explicit_gap():
    snap = _snapshot(articles=[_article(1, NOW - timedelta(hours=1))])
    ctx = build_fundamental_context(
        "ACME",
        profile=None,
        metrics=[],
        news=[ContextNewsItem.model_validate(d) for d in context_news_items(snap.news)],
        news_freshness="invalid",
        now=NOW,
    )
    assert "news" in ctx.unavailable
    entry = next(s for s in ctx.data_status if s.datatype == "news")
    assert entry.state.value == "invalid"


def test_unevaluated_news_freshness_is_flagged_not_guessed():
    snap = _snapshot(articles=[_article(1, NOW - timedelta(hours=1))])
    ctx = build_fundamental_context(
        "ACME",
        profile=None,
        metrics=[],
        news=[ContextNewsItem.model_validate(d) for d in context_news_items(snap.news)],
        news_freshness=None,
        now=NOW,
    )
    entry = next(s for s in ctx.data_status if s.datatype == "news")
    assert entry.state.value == "incomplete"
    assert "not evaluated" in (entry.detail or "")


def test_hash_deterministic_sensitive_and_wall_clock_insensitive():
    c1 = _ctx()
    c2 = _ctx()
    assert c1.context_hash == c2.context_hash
    assert c1.context_version == "m2-v2"

    changed_headline = _snapshot(
        articles=[_article(1, NOW - timedelta(hours=1), headline="Different headline")],
        bar_age=timedelta(hours=1),
    )
    assert _ctx(changed_headline).context_hash != c1.context_hash

    # Snapshot generation wall-clock is provenance, not content: identical
    # underlying data at a different generated_at keeps the SAME hash.
    later = _snapshot(articles=[_article(1, NOW - timedelta(hours=1))], bar_age=timedelta(hours=1))
    later.generated_at = NOW + timedelta(hours=2)
    assert _ctx(later).context_hash == c1.context_hash


def test_rendered_context_shows_news_and_snapshot_sections():
    text = render_context_for_model(_ctx())
    assert "RECENT NEWS" in text
    assert "[alpaca_news:a-1]" in text
    assert "feed freshness=fresh" in text
    assert "MARKET SNAPSHOT" in text
    assert "overall_state=fresh" in text
    assert "latest_bar" in text  # bounded market payload included


def test_evidence_may_cite_news_identity():
    ctx = _ctx()
    checks = check_evidence_existence(_thesis(source="a-1"), ctx)
    assert all(c.status == ClaimCheckStatus.SUPPORTED for c in checks)
    # Publisher source is citable too.
    checks = check_evidence_existence(_thesis(source="Reuters"), ctx)
    assert all(c.status == ClaimCheckStatus.SUPPORTED for c in checks)


def test_projection_roundtrip_validates_into_context_item():
    snap = _snapshot(articles=[_article(1, NOW - timedelta(hours=1))])
    items = [ContextNewsItem.model_validate(d) for d in context_news_items(snap.news)]
    assert items[0].provider_article_id == "a-1"
