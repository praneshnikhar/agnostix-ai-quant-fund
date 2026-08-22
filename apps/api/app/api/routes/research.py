"""M2 fundamental research API.

Read/research endpoints only. POST /research/{symbol}/run executes a
research cycle — it NEVER places orders or touches execution (.clinerules
§7/§27/§33). No order endpoints exist in this router.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.fundamentals_repo import (
    FinancialMetricRepository,
    ResearchDocumentRepository,
    ResearchFeedbackRepository,
    ResearchRunRepository,
)
from app.db.session import get_session
from app.services.research_service import run_research

router = APIRouter(prefix="/research", tags=["research"])


# ------------------------------------------------------------------ schemas


class RunResponse(BaseModel):
    run_id: uuid.UUID
    status: str


class ResearchRunOut(BaseModel):
    id: uuid.UUID
    symbol: str
    status: str
    created_at: object
    completed_at: object | None = None
    fundamental_view: str | None = None
    confidence: float | None = None
    critic_verdict: str | None = None
    agent_id: str | None = None
    agent_version: str | None = None
    prompt_version: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    context_version: str | None = None
    research_output: dict | None = None
    critic_output: dict | None = None
    error: str | None = None


class HistoryEntry(BaseModel):
    id: uuid.UUID
    created_at: object
    fundamental_view: str | None
    confidence: float | None
    critic_verdict: str | None
    model_provider: str | None
    model_name: str | None
    prompt_version: str | None


class MetricOut(BaseModel):
    metric: str
    value: float | None
    period_type: str
    period_end: object
    fiscal_year: int | None
    fiscal_quarter: int | None
    currency: str
    quality: str
    provider: str


class EvidenceItem(BaseModel):
    evidence_id: str
    source: str
    source_type: str
    claim_supported: str
    relevant_period: str | None = None
    url: str | None = None


class DocumentOut(BaseModel):
    document_id: str
    title: str
    document_type: str
    source: str | None = None
    url: str | None
    published_at: object | None
    retrieved_at: object


class FeedbackIn(BaseModel):
    decision: str = Field(pattern="^(APPROVE|REJECT|REQUEST_REVISION)$")
    notes: str | None = None


def _run_out(r) -> ResearchRunOut:
    ro = r.research_output or {}
    return ResearchRunOut(
        id=r.id,
        symbol=r.symbol,
        status=r.status,
        created_at=r.created_at,
        completed_at=getattr(r, "completed_at", None),
        fundamental_view=ro.get("fundamental_view"),
        confidence=ro.get("confidence"),
        critic_verdict=r.critic_verdict,
        agent_id=r.agent_id,
        agent_version=r.agent_version,
        prompt_version=r.prompt_version,
        model_provider=r.model_provider,
        model_name=r.model_name,
        context_version=(r.context_payload or {}).get("context_version"),
        research_output=ro or None,
        critic_output=r.critic_output,
        error=getattr(r, "error", None),
    )


# ------------------------------------------------------------------- reads


@router.get("/{symbol}", response_model=ResearchRunOut)
async def get_latest_research(symbol: str, session: AsyncSession = Depends(get_session)):
    run = await ResearchRunRepository(session).get_latest_completed(symbol.upper())
    if run is None:
        raise HTTPException(status_code=404, detail=f"no research for {symbol.upper()}")
    return _run_out(run)


@router.get("/{symbol}/history", response_model=list[HistoryEntry])
async def get_history(
    symbol: str,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
):
    runs = await ResearchRunRepository(session).get_history(symbol.upper(), limit)
    return [
        HistoryEntry(
            id=r.id,
            created_at=r.created_at,
            fundamental_view=(r.research_output or {}).get("fundamental_view"),
            confidence=(r.research_output or {}).get("confidence"),
            critic_verdict=r.critic_verdict,
            model_provider=r.model_provider,
            model_name=r.model_name,
            prompt_version=r.prompt_version,
        )
        for r in runs
    ]


@router.get("/{symbol}/fundamentals", response_model=list[MetricOut])
async def get_fundamentals(symbol: str, session: AsyncSession = Depends(get_session)):
    rows = await FinancialMetricRepository(session).get_metrics(symbol.upper())
    return [
        MetricOut(
            metric=m.metric,
            value=m.value,
            period_type=m.period_type,
            period_end=m.period_end,
            fiscal_year=m.fiscal_year,
            fiscal_quarter=m.fiscal_quarter,
            currency=m.currency,
            quality=m.quality,
            provider=m.provider,
        )
        for m in rows
    ]


@router.get("/{symbol}/evidence", response_model=list[EvidenceItem])
async def get_evidence(symbol: str, session: AsyncSession = Depends(get_session)):
    run = await ResearchRunRepository(session).get_latest_completed(symbol.upper())
    if run is None:
        raise HTTPException(status_code=404, detail=f"no research for {symbol.upper()}")
    evidence = (run.research_output or {}).get("evidence", [])
    return [EvidenceItem(**e) for e in evidence]


@router.get("/{symbol}/documents", response_model=list[DocumentOut])
async def get_documents(
    symbol: str,
    limit: int = Query(default=25, le=100),
    session: AsyncSession = Depends(get_session),
):
    docs = await ResearchDocumentRepository(session).get_documents(symbol.upper(), limit)
    return [
        DocumentOut(
            document_id=d.document_id,
            title=d.title,
            document_type=d.document_type,
            source=d.source,
            url=d.url,
            published_at=d.published_at,
            retrieved_at=d.retrieved_at,
        )
        for d in docs
    ]


@router.get("/runs/{run_id}", response_model=ResearchRunOut)
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    run = await ResearchRunRepository(session).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _run_out(run)


# ------------------------------------------------------------------ writes


@router.post("/{symbol}/run", response_model=RunResponse, status_code=202)
async def post_run(symbol: str, session: AsyncSession = Depends(get_session)):
    """Execute a research cycle. RESEARCH ONLY — no order capability."""
    from model_gateway.gateway import ModelGateway

    try:
        gateway = ModelGateway.from_settings()
    except Exception:
        gateway = ModelGateway()  # no providers configured → agent will fail loudly
    try:
        run_id = await run_research(session, symbol, gateway=gateway)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"research failed: {exc}") from exc
    return RunResponse(run_id=run_id, status="completed")


@router.post("/runs/{run_id}/feedback", status_code=201)
async def post_feedback(
    run_id: uuid.UUID,
    body: FeedbackIn,
    session: AsyncSession = Depends(get_session),
):
    """Human research feedback foundation (§26) — NOT connected to trading."""
    await ResearchFeedbackRepository(session).add_feedback(run_id, body.decision, body.notes, None)
    return {"status": "recorded"}
