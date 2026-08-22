"""Append-only agent event endpoints (audit trail).

GET  /agent-events — queryable audit log
POST /agent-events — append a structured event (no update/delete paths exist)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentEvent
from app.db.session import get_session
from app.schemas.contracts import AgentEventIn, AgentEventOut

router = APIRouter(prefix="/agent-events", tags=["audit"])


@router.get("", response_model=list[AgentEventOut])
async def list_events(
    agent_id: str | None = None,
    event_type: str | None = None,
    proposal_id: uuid.UUID | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AgentEventOut]:
    """Query the audit trail by agent, event type, proposal, and date range."""
    stmt = select(AgentEvent).order_by(AgentEvent.timestamp.desc()).limit(limit).offset(offset)
    if agent_id is not None:
        stmt = stmt.where(AgentEvent.agent_id == agent_id)
    if event_type is not None:
        stmt = stmt.where(AgentEvent.event_type == event_type)
    if proposal_id is not None:
        stmt = stmt.where(AgentEvent.proposal_id == proposal_id)

    rows = (await session.execute(stmt)).scalars().all()
    return [AgentEventOut.model_validate(row) for row in rows]


@router.post("", response_model=AgentEventOut, status_code=201)
async def append_event(
    event: AgentEventIn,
    session: AsyncSession = Depends(get_session),
) -> AgentEventOut:
    """Append a structured audit event. Append-only: no update/delete exists."""
    row = AgentEvent(
        agent_id=event.agent_id,
        event_type=event.event_type.value,
        payload=event.payload,
        proposal_id=event.proposal_id,
    )
    session.add(row)
    await session.flush()
    return AgentEventOut.model_validate(row)
