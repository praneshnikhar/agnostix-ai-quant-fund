"""Agent event emission — the append-only audit trail contract.

Every agent/service emits structured AgentEvent records (matching the
`agent_events` table). Free-form log messages are never the source of
truth for state transitions.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


class AgentEventRecord(BaseModel):
    """In-memory representation of one append-only audit event."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    proposal_id: uuid.UUID | None = None


# Async sink: e.g. writes to agent_events via a DB session, or queues to Redis.
EventSink = Callable[[AgentEventRecord], Awaitable[None]]


class EventSinkRegistry:
    """Pluggable sinks. M0 ships an in-memory sink; the DB sink lands with
    the first milestone that persists agent runs."""

    def __init__(self) -> None:
        self._sinks: list[EventSink] = []
        self._memory: list[AgentEventRecord] = []

    def register(self, sink: EventSink) -> None:
        self._sinks.append(sink)

    async def emit(self, record: AgentEventRecord) -> None:
        self._memory.append(record)
        for sink in self._sinks:
            await sink(record)

    def snapshot(self) -> list[AgentEventRecord]:
        return list(self._memory)


class EventEmitter(Protocol):
    """What agents use to emit events."""

    async def emit(
        self,
        agent_id: str,
        event_type: str,
        payload: dict[str, Any],
        proposal_id: uuid.UUID | None = None,
    ) -> None: ...


class RegistryEmitter:
    """Concrete emitter bound to a registry."""

    def __init__(self, registry: EventSinkRegistry) -> None:
        self._registry = registry

    async def emit(
        self,
        agent_id: str,
        event_type: str,
        payload: dict[str, Any],
        proposal_id: uuid.UUID | None = None,
    ) -> None:
        await self._registry.emit(
            AgentEventRecord(
                agent_id=agent_id,
                event_type=event_type,
                payload=payload,
                proposal_id=proposal_id,
            )
        )
