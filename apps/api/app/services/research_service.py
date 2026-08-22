"""Research orchestration service (M2).

Runs the Fundamental Research Agent + Critic cycle, persists the run,
and emits audit events. READ/research only — no order capability exists
anywhere in this module (.clinerules §7/§33).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from agents.events import EventSinkRegistry, RegistryEmitter
from fundamentals.context import build_fundamental_context
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


def _build_context(symbol: str):
    """Deterministic context from available providers.

    M2 data-source note: fixture providers back the development universe;
    live fundamental providers land with a justified data subscription.
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
    return build_fundamental_context(
        symbol.upper(),
        profile=fp.get_company_profile(symbol),
        metrics=metrics,
        earnings=earnings,
        valuation=vp.get_valuation_snapshot(symbol),
        documents=dp.get_documents(symbol),
        now=datetime.now(UTC),
    )


async def run_research(
    session: AsyncSession,
    symbol: str,
    gateway=None,
) -> uuid.UUID:
    """Execute one full research cycle. Returns the run id."""
    from app.db.repositories.fundamentals_repo import ResearchRunRepository

    emitter = RegistryEmitter(EventSinkRegistry())
    run_repo = ResearchRunRepository(session)
    run = await run_repo.create_run(symbol.upper())
    run_id = run.id
    await run_repo.mark_running(run_id)

    ctx = _build_context(symbol)
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
                "data_quality": [
                    d.model_dump(mode="json") for d in getattr(ctx, "data_quality", [])
                ],
            },
        )
        return run_id
    except Exception as exc:
        await run_repo.fail_run(run_id, repr(exc)[:1000])
        raise
