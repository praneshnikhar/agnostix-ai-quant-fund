"""Multi-model evaluation orchestration (M2.2).

Builds ONE research context via the research service, runs every configured
provider/model target against it through the evaluation runner, persists the
run + ordered report, and emits correlated audit events. READ/research only
— no order capability exists anywhere in this module (.clinerules §7/§33).

Event correlation mirrors research_service: the run row is created BEFORE any
lifecycle event is emitted; a per-run CorrelatedEmitter injects the
authoritative run_id + monotonic seq. If the context itself cannot be built,
the run fails before any row is created — comparison is impossible.
"""

from __future__ import annotations

import uuid
from contextlib import suppress

from sqlalchemy.ext.asyncio import AsyncSession

from agents.events import CorrelatedEmitter, EventSinkRegistry, RegistryEmitter
from fundamentals.research.agent import PROMPT_VERSION as AGENT_PROMPT_VERSION
from fundamentals.research.evaluation import (
    EVALUATION_AGENT_ID,
    EVALUATION_AGENT_VERSION,
    ModelTarget,
    run_evaluation,
)


async def _persist_event(session: AsyncSession, record) -> None:
    """Append one audit event to agent_events (§12/§24)."""
    from agents.events import AgentEventRecord
    from app.db.models import AgentEvent

    if not isinstance(record, AgentEventRecord):
        raise TypeError("expected AgentEventRecord")
    session.add(
        AgentEvent(
            agent_id=record.agent_id,
            event_type=record.event_type,
            payload=record.payload,
            proposal_id=record.proposal_id,
        )
    )


async def run_evaluation_for_symbol(
    session: AsyncSession,
    symbol: str,
    targets: list[ModelTarget],
    *,
    gateway_factory,
) -> uuid.UUID:
    """Execute one multi-model evaluation cycle. Returns the run id."""
    from app.core.logging import get_logger
    from app.db.repositories.fundamentals_repo import EvaluationRunRepository
    from app.services.research_service import _build_context

    logger = get_logger("evaluation_service")
    registry = EventSinkRegistry()
    registry.register(lambda rec: _persist_event(session, rec))
    base_emitter = RegistryEmitter(registry)

    # The context is built EXACTLY ONCE here and handed to the runner — the
    # runner never rebuilds it, so every model sees identical facts.
    ctx = await _build_context(session, symbol)

    repo = EvaluationRunRepository(session)
    run = await repo.create_run(
        symbol.upper(),
        context_version=ctx.context_version,
        context_hash=ctx.context_hash,
        models_config=[t.model_dump(mode="json") for t in targets],
    )
    run_id = run.id
    await repo.mark_running(run_id)

    emitter = CorrelatedEmitter(base_emitter, str(run_id))

    async def _emit(event_type: str, payload: dict) -> None:
        await emitter.emit(
            agent_id="model_evaluation_runner",
            event_type=event_type,
            payload={"symbol": symbol.upper(), **payload},
        )

    await _emit("evaluation_requested", {"models": [t.model_dump() for t in targets]})
    await _emit(
        "evaluation_context_created",
        {"context_hash": ctx.context_hash, "unavailable": ctx.unavailable},
    )
    try:
        result = await run_evaluation(
            symbol.upper(),
            targets,
            emitter=emitter,
            context=ctx,
            gateway_factory=gateway_factory,
        )
        await repo.complete_run(
            run_id,
            report=result.model_dump(mode="json"),
            prompt_version=AGENT_PROMPT_VERSION,
            agent_id=EVALUATION_AGENT_ID,
            agent_version=EVALUATION_AGENT_VERSION,
        )
        await _emit(
            "evaluation_completed",
            {
                "context_hash": result.context_hash,
                "records": len(result.records),
                "failed": sum(1 for r in result.records if r.status == "failed"),
            },
        )
        return run_id
    except Exception as exc:
        # Best-effort failure marker: an event-sink failure here must never
        # mask the original exception or corrupt the failed-run state.
        with suppress(Exception):
            await _emit("evaluation_failed", {"error": repr(exc)[:500]})
        logger.warning(
            "evaluation_run_failed",
            run_id=str(run_id),
            symbol=symbol.upper(),
            error=repr(exc)[:500],
        )
        await repo.fail_run(run_id, repr(exc)[:1000])
        raise
