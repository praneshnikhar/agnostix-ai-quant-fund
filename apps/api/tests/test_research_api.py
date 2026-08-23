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


@pytest.mark.anyio
async def test_run_research_persists_lifecycle_events(monkeypatch) -> None:
    """§24: research_requested/context_created/agent/critic/completed are
    appended to agent_events via the DB sink."""
    from app.db.repositories import fundamentals_repo as fr
    from app.services import research_service as rs
    from fundamentals.providers.fixture import FixtureFundamentalsProvider
    from fundamentals.research.schemas import InvestmentThesis

    fp = FixtureFundamentalsProvider()
    # A grounded thesis built directly from context facts (deterministic):
    # the first fixture metric is ACME annual revenue, present in any
    # context run_research builds internally.
    thesis_payload = InvestmentThesis.model_validate(
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

    class FakeRun:
        id = uuid.uuid4()

    class FakeRuns:
        def __init__(self, *a) -> None:
            pass

        async def create_run(self, symbol):
            return FakeRun()

        async def mark_running(self, rid):
            return None

        async def complete_run(self, *a, **k):
            return None

        async def fail_run(self, *a):
            return None

    monkeypatch.setattr(fr, "ResearchRunRepository", FakeRuns)
    gw = _MockGateway(thesis_payload)
    sess = RecordingSession()
    run_id = await rs.run_research(sess, "ACME", gateway=gw)  # type: ignore[arg-type]
    assert run_id == FakeRun.id
    types = [o.event_type for o in sess.added]
    assert "research_requested" in types
    assert "research_context_created" in types
    assert "research_agent_started" in types
    assert "research_critic_started" in types
    assert "research_completed" in types
    research_events = [o for o in sess.added if o.event_type.startswith("research_")]
    assert all(o.payload.get("run_id") == str(FakeRun.id) for o in research_events)
    # Ordering: per-run seq is monotonically increasing in emission order.
    seqs = [o.payload["seq"] for o in research_events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


def test_no_order_endpoints_in_research() -> None:
    from app.main import create_app

    paths = {getattr(rt, "path", "") for rt in create_app().routes}
    research_paths = [p for p in paths if p.startswith("/research")]
    assert research_paths
    for p in research_paths:
        assert "order" not in p.lower()
