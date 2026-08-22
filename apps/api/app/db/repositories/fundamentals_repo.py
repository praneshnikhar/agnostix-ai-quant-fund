"""Fundamental-data repositories (M2).

Async data-access boundary over the M2 tables. Idempotency mirrors the
domain schemas' identity constraints:

- company_profiles    : ON CONFLICT (symbol) DO UPDATE — latest wins.
- financial_metrics   : ON CONFLICT (provider, symbol, metric,
                        period_type, period_end) DO UPDATE.
- financial_statements: ON CONFLICT (provider, symbol, statement_type,
                        period_type, period_end) DO UPDATE.
- earnings_events     : ON CONFLICT (provider, symbol, period_type,
                        period_end) DO UPDATE.
- valuation_snapshots : append-only inserts.
- research_documents  : ON CONFLICT (provider, document_id) DO NOTHING
                        (first-write-wins).
- research_runs       : lifecycle rows; created pending → completed/failed.
- research_feedback   : append-only inserts.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CompanyProfileRecord,
    EarningsEventRecord,
    FinancialMetricRecord,
    FinancialStatementRecord,
    ResearchDocumentRecord,
    ResearchFeedback,
    ResearchRun,
    ValuationSnapshotRecord,
)


class CompanyProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_profile(self, values: dict) -> None:
        stmt = pg_insert(CompanyProfileRecord).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "name": stmt.excluded.name,
                "exchange": stmt.excluded.exchange,
                "sector": stmt.excluded.sector,
                "industry": stmt.excluded.industry,
                "description": stmt.excluded.description,
                "employees": stmt.excluded.employees,
                "currency": stmt.excluded.currency,
                "provider": stmt.excluded.provider,
                "received_at": stmt.excluded.received_at,
            },
        )
        await self._session.execute(stmt)

    async def get_by_symbol(self, symbol: str) -> CompanyProfileRecord | None:
        result = await self._session.execute(
            select(CompanyProfileRecord).where(
                CompanyProfileRecord.symbol == symbol.upper()
            )
        )
        return result.scalar_one_or_none()


class FinancialMetricRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_metrics(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        stmt = pg_insert(FinancialMetricRecord).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["provider", "symbol", "metric", "period_type", "period_end"],
            set_={
                "value": stmt.excluded.value,
                "fiscal_year": stmt.excluded.fiscal_year,
                "fiscal_quarter": stmt.excluded.fiscal_quarter,
                "currency": stmt.excluded.currency,
                "units": stmt.excluded.units,
                "quality": stmt.excluded.quality,
                "received_at": stmt.excluded.received_at,
            },
        )
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_metrics(self, symbol: str, period_type: str | None = None) -> list[FinancialMetricRecord]:
        q = (
            select(FinancialMetricRecord)
            .where(FinancialMetricRecord.symbol == symbol.upper())
            .order_by(FinancialMetricRecord.period_end.desc(), FinancialMetricRecord.metric)
        )
        if period_type:
            q = q.where(FinancialMetricRecord.period_type == period_type)
        result = await self._session.execute(q)
        return list(result.scalars())


class FinancialStatementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_statements(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        stmt = pg_insert(FinancialStatementRecord).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["provider", "symbol", "statement_type", "period_type", "period_end"],
            set_={
                "line_items": stmt.excluded.line_items,
                "fiscal_year": stmt.excluded.fiscal_year,
                "fiscal_quarter": stmt.excluded.fiscal_quarter,
                "currency": stmt.excluded.currency,
                "units": stmt.excluded.units,
                "quality": stmt.excluded.quality,
                "received_at": stmt.excluded.received_at,
            },
        )
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_statements(
        self, symbol: str, statement_type: str | None = None
    ) -> list[FinancialStatementRecord]:
        q = (
            select(FinancialStatementRecord)
            .where(FinancialStatementRecord.symbol == symbol.upper())
            .order_by(FinancialStatementRecord.period_end.desc())
        )
        if statement_type:
            q = q.where(FinancialStatementRecord.statement_type == statement_type)
        result = await self._session.execute(q)
        return list(result.scalars())


class EarningsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_events(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        stmt = pg_insert(EarningsEventRecord).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["provider", "symbol", "period_type", "period_end"],
            set_={
                "event_time": stmt.excluded.event_time,
                "eps_actual": stmt.excluded.eps_actual,
                "eps_estimate": stmt.excluded.eps_estimate,
                "revenue_actual": stmt.excluded.revenue_actual,
                "revenue_estimate": stmt.excluded.revenue_estimate,
                "received_at": stmt.excluded.received_at,
            },
        )
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_events(self, symbol: str, limit: int = 12) -> list[EarningsEventRecord]:
        result = await self._session.execute(
            select(EarningsEventRecord)
            .where(EarningsEventRecord.symbol == symbol.upper())
            .order_by(EarningsEventRecord.event_time.desc())
            .limit(limit)
        )
        return list(result.scalars())


class ValuationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_snapshot(self, values: dict) -> None:
        self._session.add(ValuationSnapshotRecord(**values))
        await self._session.flush()

    async def get_latest(self, symbol: str) -> ValuationSnapshotRecord | None:
        result = await self._session.execute(
            select(ValuationSnapshotRecord)
            .where(ValuationSnapshotRecord.symbol == symbol.upper())
            .order_by(ValuationSnapshotRecord.as_of.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class ResearchDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_documents(self, rows: list[dict]) -> int:
        """First-write-wins on (provider, document_id)."""
        if not rows:
            return 0
        stmt = pg_insert(ResearchDocumentRecord).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["provider", "document_id"])
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_documents(self, symbol: str, limit: int = 25) -> list[ResearchDocumentRecord]:
        result = await self._session.execute(
            select(ResearchDocumentRecord)
            .where(ResearchDocumentRecord.symbol == symbol.upper())
            .order_by(ResearchDocumentRecord.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars())


class ResearchRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(self, symbol: str, context_version: str = "v0") -> ResearchRun:
        run = ResearchRun(symbol=symbol.upper(), context_version=context_version)
        self._session.add(run)
        await self._session.flush()
        return run

    async def mark_running(self, run_id: uuid.UUID) -> None:
        run = await self.get_run(run_id)
        if run is not None:
            run.status = "running"

    async def complete_run(
        self,
        run_id: uuid.UUID,
        research_output: dict,
        critic_output: dict | None,
        critic_verdict: str | None,
        *,
        agent_id: str | None = None,
        agent_version: str | None = None,
        prompt_version: str | None = None,
        model_provider: str | None = None,
        model_name: str | None = None,
        context_payload: dict | None = None,
    ) -> None:
        run = await self.get_run(run_id)
        if run is None:
            return
        run.status = "completed"
        run.completed_at = datetime.now(run.created_at.tzinfo) if run.created_at else None
        run.research_output = research_output
        run.critic_output = critic_output
        run.critic_verdict = critic_verdict
        run.agent_id = agent_id
        run.agent_version = agent_version
        run.prompt_version = prompt_version
        run.model_provider = model_provider
        run.model_name = model_name
        if context_payload is not None:
            run.context_payload = context_payload

    async def fail_run(self, run_id: uuid.UUID, error: str) -> None:
        run = await self.get_run(run_id)
        if run is None:
            return
        run.status = "failed"
        run.completed_at = datetime.now(run.created_at.tzinfo) if run.created_at else None
        run.error = error[:2000]

    async def get_run(self, run_id: uuid.UUID) -> ResearchRun | None:
        result = await self._session.execute(
            select(ResearchRun).where(ResearchRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_completed(self, symbol: str) -> ResearchRun | None:
        result = await self._session.execute(
            select(ResearchRun)
            .where(
                ResearchRun.symbol == symbol.upper(),
                ResearchRun.status == "completed",
            )
            .order_by(ResearchRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history(self, symbol: str, limit: int = 50) -> list[ResearchRun]:
        result = await self._session.execute(
            select(ResearchRun)
            .where(ResearchRun.symbol == symbol.upper())
            .order_by(ResearchRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())


class ResearchFeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_feedback(
        self, run_id: uuid.UUID, decision: str, notes: str | None, user_id: uuid.UUID | None
    ) -> ResearchFeedback:
        fb = ResearchFeedback(run_id=run_id, decision=decision, notes=notes, user_id=user_id)
        self._session.add(fb)
        await self._session.flush()
        return fb

    async def get_for_run(self, run_id: uuid.UUID) -> list[ResearchFeedback]:
        result = await self._session.execute(
            select(ResearchFeedback)
            .where(ResearchFeedback.run_id == run_id)
            .order_by(ResearchFeedback.decided_at.desc())
        )
        return list(result.scalars())