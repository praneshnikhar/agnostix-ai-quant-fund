"""Research orchestration service (M2).

Runs the Fundamental Research Agent + Critic cycle, persists the run,
and emits audit events. READ/research only — no order capability exists
anywhere in this module (.clinerules §7/§33).

Event correlation: the run row is created BEFORE any lifecycle event is
emitted; every event (orchestrator-, agent-, or critic-emitted) flows
through a per-run CorrelatedEmitter that injects the authoritative
run_id + monotonic seq into the payload. All events are appended to
agent_events via a DB sink on the same session/transaction as the run
row, so ordering follows emission order and persistence is atomic with
the run outcome.
"""

from __future__ import annotations

import uuid
from contextlib import suppress
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from agents.events import CorrelatedEmitter, EventSinkRegistry, RegistryEmitter
from fundamentals.context import ContextNewsItem, build_fundamental_context
from fundamentals.metrics import earnings_surprise
from fundamentals.providers.fixture import (
    FixtureDocumentsProvider,
    FixtureEarningsProvider,
    FixtureFundamentalsProvider,
    FixtureValuationProvider,
)
from fundamentals.research.agent import FundamentalResearchAgent
from fundamentals.research.critic import CriticInput, FundamentalResearchCritic
from fundamentals.schemas import EarningsResult
from market_data.snapshot import (
    build_snapshot,
    context_news_items,
    snapshot_research_summary,
)


async def _persist_event(session: AsyncSession, record) -> None:
    """Append one audit event to agent_events (§12/§24).

    Runs on the same session as the research run row: events commit
    atomically with the run outcome. Failures propagate loudly on the
    success path — silent event loss is worse than a failed run.
    """
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


async def _build_context(
    session: AsyncSession, symbol: str, *, now: datetime | None = None
):
    """Deterministic context from available providers + M1 market intel.

    M2 data-source note: fixture providers back the fundamental universe;
    live fundamental providers land with a justified data subscription.
    News + MarketSnapshot flow through the established M1 service layer
    (build_snapshot) — never ad-hoc queries. When either is absent or
    stale, the context records the gap explicitly; nothing is fabricated.
    Zero LLM calls happen here (§12: deterministic assembly only).
    """
    fp = FixtureFundamentalsProvider()
    ep = FixtureEarningsProvider()
    vp = FixtureValuationProvider()
    dp = FixtureDocumentsProvider()
    metrics = fp.get_financial_metrics(symbol)
    earnings = []
    for e in ep.get_earnings_events(symbol):
        s, p = earnings_surprise(e.eps_actual, e.eps_estimate)
        earnings.append(EarningsResult(event=e, eps_surprise=s, eps_surprise_pct=p))

    snapshot = await build_snapshot(session, symbol, now=now)
    news_status = next((d for d in snapshot.data_quality if d.datatype == "news"), None)

    return build_fundamental_context(
        symbol.upper(),
        profile=fp.get_company_profile(symbol),
        metrics=metrics,
        earnings=earnings,
        valuation=vp.get_valuation_snapshot(symbol),
        documents=dp.get_documents(symbol),
        news=[
            ContextNewsItem.model_validate(d) for d in context_news_items(snapshot.news)
        ],
        news_freshness=news_status.state.value if news_status else None,
        market_snapshot_summary=snapshot_research_summary(snapshot),
        market_snapshot_generated_at=snapshot.generated_at,
        now=now or datetime.now(UTC),
    )


async def run_research(
    session: AsyncSession,
    symbol: str,
    gateway=None,
) -> uuid.UUID:
    """Execute one full research cycle. Returns the run id."""
    from app.core.logging import get_logger
    from app.db.repositories.fundamentals_repo import ResearchRunRepository

    logger = get_logger("research_service")
    registry = EventSinkRegistry()
    registry.register(lambda rec: _persist_event(session, rec))
    base_emitter = RegistryEmitter(registry)

    # Run id exists before ANY lifecycle event is emitted, so every event
    # can be correlated to its research run.
    run_repo = ResearchRunRepository(session)
    run = await run_repo.create_run(symbol.upper())
    run_id = run.id
    await run_repo.mark_running(run_id)

    emitter = CorrelatedEmitter(base_emitter, str(run_id))

    async def _emit(event_type: str, payload: dict) -> None:
        await emitter.emit(
            agent_id="research_orchestrator",
            event_type=event_type,
            payload={"symbol": symbol.upper(), **payload},
        )

    await _emit("research_requested", {})
    ctx = await _build_context(session, symbol)
    await _emit("research_context_created", {"context_hash": ctx.context_hash})
    try:
        agent = FundamentalResearchAgent(gateway, emitter)
        result = await agent.run(ctx)
        critic = FundamentalResearchCritic(emitter)
        critic_result = await critic.run(CriticInput(context=ctx, thesis=result.thesis))

        await run_repo.complete_run(
            run_id,
            research_output=result.thesis.model_dump(mode="json"),
            critic_output=critic_result.review.model_dump(mode="json"),
            critic_verdict=critic_result.review.verdict.value,
            agent_id=result.agent_id,
            agent_version=result.agent_version,
            prompt_version=result.prompt_version,
            model_provider=result.provider,
            model_name=result.model,
            context_payload={
                "context_version": result.context_version,
                "context_hash": result.context_hash,
                "unavailable": ctx.unavailable,
                "data_status": [d.model_dump(mode="json") for d in ctx.data_status],
            },
        )
        await _emit("research_completed", {"critic_verdict": critic_result.review.verdict.value})
        return run_id
    except Exception as exc:
        # Best-effort failure marker: an event-sink failure here must never
        # mask the original research exception or corrupt the failed-run state.
        with suppress(Exception):
            await _emit("research_agent_failed", {"error": repr(exc)[:500]})
        logger.warning(
            "research_run_failed",
            run_id=str(run_id),
            symbol=symbol.upper(),
            error=repr(exc)[:500],
        )
        await run_repo.fail_run(run_id, repr(exc)[:1000])
        raise
