"""Fundamental provider ABCs (M2).

Mirrors market_data.providers.base: abstract interfaces returning internal
schemas. Implementations must never fabricate responses — unavailable data
is returned as empty/None, never invented.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from fundamentals.schemas import (
    CompanyProfile,
    EarningsEvent,
    FinancialMetric,
    FinancialStatement,
    ResearchDocument,
    ValuationSnapshot,
)


class FundamentalsProvider(ABC):
    """Company profile + financial metrics/statements."""

    @abstractmethod
    def get_company_profile(self, symbol: str) -> CompanyProfile | None: ...

    @abstractmethod
    def get_financial_metrics(
        self, symbol: str, period_type: str | None = None, limit: int = 20
    ) -> list[FinancialMetric]: ...

    @abstractmethod
    def get_statements(
        self, symbol: str, statement_type: str | None = None, limit: int = 8
    ) -> list[FinancialStatement]: ...


class EarningsProvider(ABC):
    @abstractmethod
    def get_earnings_events(
        self, symbol: str, limit: int = 12
    ) -> list[EarningsEvent]: ...


class ValuationProvider(ABC):
    @abstractmethod
    def get_valuation_snapshot(self, symbol: str) -> ValuationSnapshot | None: ...


class FinancialDocumentsProvider(ABC):
    @abstractmethod
    def get_documents(
        self,
        symbol: str,
        since: date | None = None,
        limit: int = 25,
    ) -> list[ResearchDocument]: ...