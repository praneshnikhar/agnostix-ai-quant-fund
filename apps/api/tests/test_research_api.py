"""M2 research API tests — deterministic; repositories faked via monkeypatch."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

T0 = datetime.now(UTC) - timedelta(hours=1)
RUN_ID = uuid.uuid4()

THESIS = {
    "symbol": "ACME",
    "research_timestamp": T0.isoformat(),
    "fundamental_view": "BULLISH",
    "confidence": 0.7,
    "investment_thesis": "Strong growth.",
    "evidence": [
        {
            "evidence_id": "ev1",
            "source": "acme-fy2025-10k",
            "source_type": "document",
            "claim_supported": "growth",
        }
    ],
}


class _Rec:
    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class FakeSession:
    async def commit(self) -> None:
        return None


def _run(**over):
    base = dict(
        id=RUN_ID,
        symbol="ACME",
        status="completed",
        created_at=T0,
        completed_at=T0,
        critic_verdict="PASS",
        agent_id="fundamental_research_agent_v1",
        agent_version="v1",
        prompt_version="m2-fundamental-v1",
        model_provider="mock",
        model_name="mock-model-1",
        context_payload={"context_version": "m2-v1"},
        research_output=THESIS,
        critic_output={"verdict": "PASS"},
        error=None,
    )
    base.update(over)
    return _Rec(**base)


@pytest.fixture()
def seeded(monkeypatch):
    from app.api.routes import research as r

    run = _run()
    metric = _Rec(
        metric="revenue",
        value=115200.0,
        period_type="annual",
        period_end=T0.date(),
        fiscal_year=2025,
        fiscal_quarter=None,
        currency="USD",
        quality="ok",
        provider="fixture",
    )
    doc = _Rec(
        document_id="acme-fy2025-10k",
        title="FY2025 10-K",
        document_type="filing",
        source="sec",
        url=None,
        published_at=T0,
        retrieved_at=T0,
    )

    class Runs:
        def __init__(self, *a) -> None:
            pass

        async def get_latest_completed(self, symbol):
            return run if symbol == "ACME" else None

        async def get_history(self, symbol, limit=50):
            return [run] if symbol == "ACME" else []

        async def get_run(self, rid):
            return run if rid == RUN_ID else None

    class Metrics:
        def __init__(self, *a) -> None:
            pass

        async def get_metrics(self, symbol):
            return [metric]

    class Docs:
        def __init__(self, *a) -> None:
            pass

        async def get_documents(self, symbol, limit=25):
            return [doc]

    class Feedback:
        def __init__(self, *a) -> None:
            pass

        async def add_feedback(self, *a) -> None:
            return None

    monkeypatch.setattr(r, "ResearchRunRepository", Runs)
    monkeypatch.setattr(r, "FinancialMetricRepository", Metrics)
    monkeypatch.setattr(r, "ResearchDocumentRepository", Docs)
    monkeypatch.setattr(r, "ResearchFeedbackRepository", Feedback)
    return r


@pytest.mark.anyio
async def test_get_latest_research(seeded) -> None:
    out = await seeded.get_latest_research("ACME", FakeSession())
    assert out.fundamental_view == "BULLISH"
    assert out.confidence == 0.7
    assert out.model_provider == "mock"


@pytest.mark.anyio
async def test_get_latest_research_404(seeded) -> None:
    import fastapi

    with pytest.raises(fastapi.HTTPException) as ei:
        await seeded.get_latest_research("ZZZZ", FakeSession())
    assert ei.value.status_code == 404


@pytest.mark.anyio
async def test_history_and_run(seeded) -> None:
    hist = await seeded.get_history("ACME", limit=10, session=FakeSession())
    assert hist[0].critic_verdict == "PASS"
    one = await seeded.get_run(RUN_ID, session=FakeSession())
    assert one.id == RUN_ID


@pytest.mark.anyio
async def test_fundamentals_documents_evidence(seeded) -> None:
    s = FakeSession()
    metrics = await seeded.get_fundamentals("ACME", session=s)
    assert metrics[0].value == 115200.0 and metrics[0].quality == "ok"
    docs = await seeded.get_documents("ACME", session=s)
    assert docs[0].document_id == "acme-fy2025-10k"
    ev = await seeded.get_evidence("ACME", session=s)
    assert ev[0].source == "acme-fy2025-10k"


@pytest.mark.anyio
async def test_feedback_validation(seeded) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        seeded.FeedbackIn(decision="PLACE_ORDER")
    fb = seeded.FeedbackIn(decision="APPROVE", notes="solid grounding")
    assert fb.decision == "APPROVE"


class _MockGateway:
    class ModelClass:
        REASONING = "reasoning"

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def run(self, **kwargs):
        return {
            "content": None,
            "structured": self._payload,
            "provider": "mock",
            "model": "mock-model-1",
            "latency_ms": 5,
        }


class RecordingSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None


# ------------------------------------------------------- M2.1 market fakes


def _news_row(i: int) -> _Rec:
    return _Rec(
        provider_article_id=f"n-{i}",
        headline=f"Headline {i}",
        summary=None,
        source="Reuters",
        url=None,
        symbols=["ACME"],
        published_at=T0 - timedelta(minutes=i),
        received_at=T0 - timedelta(minutes=i),
        provider="alpaca_news",
    )


def _market_repo_fakes(
    monkeypatch,
    *,
    news_rows: list[_Rec] | None = None,
    with_security: bool = True,
    with_bar: bool = True,
    with_quote: bool = True,
    with_trades: bool = True,
) -> dict:
    """Fake the M1 market-data repositories so build_snapshot runs without
    a database while exercising the REAL snapshot/projection logic.

    Quote/trade timestamps are computed at call time: their freshness
    thresholds (60s / 300s) are tighter than any fixed module constant can
    guarantee, and the tests assert on stable OUTCOMES (fresh), not instants.
    """
    from app.db.repositories import market_data_repo as mdr

    calls: dict = {"news_query": None}
    sec = _Rec(name="Acme Corp", exchange="NASDAQ", asset_class="us_equity", status="active")
    bar = _Rec(
        symbol="ACME",
        timeframe="1Day",
        event_time=T0,
        open=90.0,
        high=92.0,
        low=89.0,
        close=91.20,
        volume=1_000_000.0,
        provider="alpaca_market_data",
        received_at=T0,
    )

    class FakeSecurityRepo:
        def __init__(self, *a) -> None:
            pass

        async def get_by_symbol(self, symbol):
            return sec if (with_security and symbol == "ACME") else None

    class FakeBarRepo:
        def __init__(self, *a) -> None:
            pass

        async def get_latest_bar(self, symbol):
            return bar if (with_bar and symbol == "ACME") else None

    class FakeQuoteRepo:
        def __init__(self, *a) -> None:
            pass

        async def get_latest_quote(self, symbol):
            if not (with_quote and symbol == "ACME"):
                return None
            t = datetime.now(UTC) - timedelta(seconds=5)
            return _Rec(
                symbol=symbol,
                event_time=t,
                bid_price=91.0,
                bid_size=100.0,
                ask_price=91.4,
                ask_size=100.0,
                last_price=91.20,
                provider="alpaca_market_data",
                received_at=t,
            )

    class FakeTradeRepo:
        def __init__(self, *a) -> None:
            pass

        async def get_recent_trades(self, symbol, limit=50):
            if not (with_trades and symbol == "ACME"):
                return []
            t = datetime.now(UTC) - timedelta(seconds=10)
            return [
                _Rec(
                    symbol=symbol,
                    event_time=t,
                    price=91.15,
                    size=50.0,
                    conditions=[],
                    provider="alpaca_market_data",
                    provider_trade_id="t-1",
                    received_at=t,
                )
            ]

    class FakeNewsRepo:
        def __init__(self, *a) -> None:
            pass

        async def get_recent_news(self, symbols=None, limit=50, since=None):
            calls["news_query"] = {"symbols": symbols, "limit": limit}
            return list(news_rows or [])

    monkeypatch.setattr(mdr, "SecurityRepository", FakeSecurityRepo)
    monkeypatch.setattr(mdr, "BarRepository", FakeBarRepo)
    monkeypatch.setattr(mdr, "QuoteRepository", FakeQuoteRepo)
    monkeypatch.setattr(mdr, "TradeRepository", FakeTradeRepo)
    monkeypatch.setattr(mdr, "NewsRepository", FakeNewsRepo)
    return calls


def _grounded_thesis_payload() -> dict:
    """A thesis grounded in fixture facts — deterministic across runs."""
    from fundamentals.providers.fixture import FixtureFundamentalsProvider
    from fundamentals.research.schemas import InvestmentThesis

    fp = FixtureFundamentalsProvider()
    return InvestmentThesis.model_validate(
        {
            "symbol": "ACME",
            "research_timestamp": T0.isoformat(),
            "fundamental_view": "BULLISH",
            "confidence": 0.6,
            "investment_thesis": "Growth supported by reported revenue.",
            "financial_assessment": {"area": "financial", "summary": "ok"},
            "growth_assessment": {
                "area": "growth",
                "summary": "growing",
                "statements": [
                    {
                        "kind": "FACT",
                        "text": f"Revenue was {fp.get_financial_metrics('ACME')[0].value:,.1f}.",
                        "evidence_ids": ["ev1"],
                    }
                ],
            },
            "profitability_assessment": {"area": "profitability", "summary": "ok"},
            "cash_flow_assessment": {"area": "cash_flow", "summary": "ok"},
            "balance_sheet_assessment": {"area": "balance_sheet", "summary": "ok"},
            "valuation_assessment": {"area": "valuation", "summary": "ok"},
            "evidence": [
                {
                    "evidence_id": "ev1",
                    "source": "acme-fy2025-10k",
                    "source_type": "document",
                    "claim_supported": "growth",
                }
            ],
        }
    ).model_dump(mode="json")


class _FakeRun:
    id = uuid.uuid4()


class _FakeRuns:
    def __init__(self, *a) -> None:
        self.completed: dict = {}

    async def create_run(self, symbol):
        return _FakeRun()

    async def mark_running(self, rid):
        return None

    async def complete_run(self, run_id, **kwargs):
        self.completed = kwargs
        return None

    async def fail_run(self, *a):
        return None


@pytest.mark.anyio
async def test_run_research_persists_lifecycle_events(monkeypatch) -> None:
    """§24: research_requested/context_created/agent/critic/completed are
    appended to agent_events via the DB sink."""
    from app.db.repositories import fundamentals_repo as fr
    from app.services import research_service as rs

    _market_repo_fakes(monkeypatch, news_rows=[_news_row(1)])

    class FakeRuns(_FakeRuns):
        pass

    monkeypatch.setattr(fr, "ResearchRunRepository", FakeRuns)
    gw = _MockGateway(_grounded_thesis_payload())
    sess = RecordingSession()
    run_id = await rs.run_research(sess, "ACME", gateway=gw)  # type: ignore[arg-type]
    assert run_id == _FakeRun.id
    types = [o.event_type for o in sess.added]
    assert "research_requested" in types
    assert "research_context_created" in types
    assert "research_agent_started" in types
    assert "research_critic_started" in types
    assert "research_completed" in types
    research_events = [o for o in sess.added if o.event_type.startswith("research_")]
    assert all(o.payload.get("run_id") == str(_FakeRun.id) for o in research_events)
    # Ordering: per-run seq is monotonically increasing in emission order.
    seqs = [o.payload["seq"] for o in research_events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


@pytest.mark.anyio
async def test_run_research_context_integrates_news_and_snapshot(monkeypatch) -> None:
    """M2.1: the persisted context carries M1 news + snapshot status, and
    news is queried for the requested symbol only."""
    from app.db.repositories import fundamentals_repo as fr
    from app.services import research_service as rs

    fake_runs = _FakeRuns()
    monkeypatch.setattr(fr, "ResearchRunRepository", lambda *a: fake_runs)
    calls = _market_repo_fakes(monkeypatch, news_rows=[_news_row(1), _news_row(2)])

    gw = _MockGateway(_grounded_thesis_payload())
    await rs.run_research(RecordingSession(), "ACME", gateway=gw)  # type: ignore[arg-type]

    payload = fake_runs.completed["context_payload"]
    assert payload["context_version"] == "m2-v2"
    types = {d["datatype"]: d["state"] for d in payload["data_status"]}
    assert types["news"] == "ok"  # fresh feed -> ok
    assert types["market_snapshot"] == "ok"
    assert "news" not in payload["unavailable"]
    assert "market_snapshot" not in payload["unavailable"]
    # Relevance filter: news fetched for the requested symbol only.
    assert calls["news_query"]["symbols"] == ["ACME"]


@pytest.mark.anyio
async def test_run_research_marks_missing_news_and_stale_market(monkeypatch) -> None:
    """M2.1: absent news / stale market data become explicit gaps — never
    fabricated, never silently omitted."""
    from app.db.repositories import fundamentals_repo as fr
    from app.services import research_service as rs

    fake_runs = _FakeRuns()
    monkeypatch.setattr(fr, "ResearchRunRepository", lambda *a: fake_runs)
    # No news/security/bar/quote/trade rows -> every datatype missing.
    _market_repo_fakes(
        monkeypatch,
        news_rows=[],
        with_security=False,
        with_bar=False,
        with_quote=False,
        with_trades=False,
    )

    gw = _MockGateway(_grounded_thesis_payload())
    await rs.run_research(RecordingSession(), "ACME", gateway=gw)  # type: ignore[arg-type]

    payload = fake_runs.completed["context_payload"]
    types = {d["datatype"]: d["state"] for d in payload["data_status"]}
    assert types["news"] == "unavailable"
    assert types["market_snapshot"] == "unavailable"
    assert "news" in payload["unavailable"]
    assert "market_snapshot" in payload["unavailable"]


def test_no_order_endpoints_in_research() -> None:
    from app.main import create_app

    paths = list(create_app().openapi()["paths"].keys())
    research_paths = [p for p in paths if p.startswith("/research")]
    assert research_paths
    for p in research_paths:
        assert "order" not in p.lower()
