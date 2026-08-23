"""M2.2 evaluation-service tests — deterministic; repositories faked.

Covers orchestration + persistence + audit-event correlation. All gateways
are mocks; no live providers, no network.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

T0 = datetime.now(UTC) - timedelta(hours=1)


class _Rec:
    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class RecordingSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None


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


def _fake_market_repos(monkeypatch) -> None:
    """Fake M1 market-data repositories so context building runs without DB."""
    from app.db.repositories import market_data_repo as mdr

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
            return sec if symbol == "ACME" else None

    class FakeBarRepo:
        def __init__(self, *a) -> None:
            pass

        async def get_latest_bar(self, symbol):
            return bar if symbol == "ACME" else None

    class FakeQuoteRepo:
        def __init__(self, *a) -> None:
            pass

        async def get_latest_quote(self, symbol):
            t = datetime.now(UTC)
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
            t = datetime.now(UTC)
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
            return [_news_row(1), _news_row(2)]

    monkeypatch.setattr(mdr, "SecurityRepository", FakeSecurityRepo)
    monkeypatch.setattr(mdr, "BarRepository", FakeBarRepo)
    monkeypatch.setattr(mdr, "QuoteRepository", FakeQuoteRepo)
    monkeypatch.setattr(mdr, "TradeRepository", FakeTradeRepo)
    monkeypatch.setattr(mdr, "NewsRepository", FakeNewsRepo)


def _grounded_thesis_payload() -> dict:
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


class _MockGateway:
    class ModelClass:
        REASONING = "reasoning"

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "content": None,
            "structured": self._payload,
            "provider": "mock",
            "model": "mock-model-1",
            "latency_ms": 5,
        }


class _FakeEvaluationRun:
    id = uuid.uuid4()


class _FakeEvaluationRuns:
    def __init__(self, *a) -> None:
        self.created: dict | None = None
        self.completed: dict | None = None
        self.failed: str | None = None

    async def create_run(self, symbol, *, context_version, context_hash, models_config):
        self.created = {
            "symbol": symbol,
            "context_version": context_version,
            "context_hash": context_hash,
            "models_config": models_config,
        }
        return _FakeEvaluationRun()

    async def mark_running(self, rid):
        return None

    async def complete_run(self, run_id, **kwargs):
        self.completed = kwargs
        return None

    async def fail_run(self, run_id, error):
        self.failed = error
        return None


@pytest.mark.anyio
async def test_evaluation_service_persists_and_emits(monkeypatch) -> None:
    """One row + correlated events; report carries per-model records."""
    from app.db.repositories import fundamentals_repo as fr
    from app.services import evaluation_service as es
    from fundamentals.research.evaluation import ModelTarget

    _fake_market_repos(monkeypatch)
    fake_runs = _FakeEvaluationRuns()
    monkeypatch.setattr(fr, "EvaluationRunRepository", lambda *a: fake_runs)

    targets = [
        ModelTarget(provider="alpha", model="big-model"),
        ModelTarget(provider="beta", model="small-model"),
    ]
    gateways = {
        (t.provider, t.model): _MockGateway(_grounded_thesis_payload()) for t in targets
    }

    sess = RecordingSession()
    run_id = await es.run_evaluation_for_symbol(
        sess,  # type: ignore[arg-type]
        "ACME",
        targets,
        gateway_factory=lambda target: gateways[(target.provider, target.model)],
    )
    assert run_id == _FakeEvaluationRun.id

    # Row created BEFORE events, with reproduction metadata.
    assert fake_runs.created is not None
    assert fake_runs.created["symbol"] == "ACME"
    assert fake_runs.created["context_version"] == "m2-v2"
    assert fake_runs.created["context_hash"]
    assert [m["provider"] for m in fake_runs.created["models_config"]] == ["alpha", "beta"]

    # Completed with an ordered comparable report.
    assert fake_runs.completed is not None
    report = fake_runs.completed["report"]
    assert [(r["provider"], r["status"]) for r in report["records"]] == [
        ("alpha", "completed"),
        ("beta", "completed"),
    ]
    hashes = {r["context_hash"] for r in report["records"]}
    versions = {r["context_version"] for r in report["records"]}
    assert hashes == {fake_runs.created["context_hash"]}
    assert versions == {"m2-v2"}
    assert fake_runs.completed["prompt_version"] == "m2-fundamental-v1"

    # Correlated lifecycle events on the same session/transaction.
    types = [o.event_type for o in sess.added]
    assert "evaluation_requested" in types
    assert "evaluation_context_created" in types
    assert "evaluation_model_finished" in types
    assert "evaluation_completed" in types
    eval_events = [o for o in sess.added if o.event_type.startswith("evaluation_")]
    assert all(o.payload.get("run_id") == str(_FakeEvaluationRun.id) for o in eval_events)
    seqs = [o.payload["seq"] for o in eval_events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


@pytest.mark.anyio
async def test_evaluation_service_isolates_provider_failure(monkeypatch) -> None:
    """A dead provider fails only its own record; the run still completes."""
    from app.db.repositories import fundamentals_repo as fr
    from app.services import evaluation_service as es
    from fundamentals.research.evaluation import ModelTarget

    _fake_market_repos(monkeypatch)
    fake_runs = _FakeEvaluationRuns()
    monkeypatch.setattr(fr, "EvaluationRunRepository", lambda *a: fake_runs)

    targets = [
        ModelTarget(provider="ghost", model="missing"),
        ModelTarget(provider="real", model="works"),
    ]
    real = _MockGateway(_grounded_thesis_payload())

    def factory(target):
        if target.provider == "real":
            return real
        raise ValueError("not configured")

    sess = RecordingSession()
    await es.run_evaluation_for_symbol(
        sess,  # type: ignore[arg-type]
        "ACME",
        targets,
        gateway_factory=factory,
    )

    assert fake_runs.failed is None  # run NOT failed
    assert fake_runs.completed is not None
    report = fake_runs.completed["report"]
    statuses = {r["provider"]: r["status"] for r in report["records"]}
    assert statuses == {"ghost": "failed", "real": "completed"}
    ghost = next(r for r in report["records"] if r["provider"] == "ghost")
    assert "gateway unavailable" in ghost["error"]


@pytest.mark.anyio
async def test_evaluation_service_fails_when_context_unbuildable(monkeypatch) -> None:
    """If the context cannot be created, the whole run fails loudly."""
    from app.db.repositories import fundamentals_repo as fr
    from app.services import evaluation_service as es
    from fundamentals.research.evaluation import ModelTarget

    # No market-data fakes: RecordingSession cannot execute queries.
    fake_runs = _FakeEvaluationRuns()
    monkeypatch.setattr(fr, "EvaluationRunRepository", lambda *a: fake_runs)

    sess = RecordingSession()
    # RecordingSession has no execute(): context building fails loudly.
    with pytest.raises(AttributeError):
        await es.run_evaluation_for_symbol(
            sess,  # type: ignore[arg-type]
            "ACME",
            [ModelTarget(provider="p", model="m")],
            gateway_factory=lambda t: _MockGateway(_grounded_thesis_payload()),
        )
    # No row was ever created: comparison is impossible without a context.
    assert fake_runs.created is None
