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


def test_no_order_endpoints_in_research() -> None:
    from app.main import create_app

    paths = {getattr(rt, "path", "") for rt in create_app().routes}
    research_paths = [p for p in paths if p.startswith("/research")]
    assert research_paths
    for p in research_paths:
        assert "order" not in p.lower()
