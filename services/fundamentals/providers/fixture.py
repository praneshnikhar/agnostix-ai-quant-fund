"""Deterministic fixture provider (M2).

Serves a small, clearly-labeled synthetic universe for development and
testing. Fixture data is NEVER presented as live market data — every
record is provider-tagged "fixture" and the UI labels it as such
(.clinerules §33 NO FABRICATION).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fundamentals.providers.base import (
    EarningsProvider,
    FinancialDocumentsProvider,
    FundamentalsProvider,
    ValuationProvider,
)
from fundamentals.schemas import (
    CompanyProfile,
    DocumentType,
    EarningsEvent,
    FinancialMetric,
    FinancialPeriod,
    FinancialStatement,
    PeriodType,
    ProviderInfo,
    ResearchDocument,
    StatementType,
    ValuationSnapshot,
)

PROVIDER = "fixture"
_RECEIVED = datetime(2026, 8, 1, tzinfo=UTC)


def _prov(record_id: str | None = None) -> ProviderInfo:
    return ProviderInfo(provider=PROVIDER, raw_record_id=record_id)


def _annual(symbol: str, metric: str, fy: int, value: float) -> FinancialMetric:
    return FinancialMetric(
        symbol=symbol,
        metric=metric,
        value=value,
        period=FinancialPeriod(
            period_type=PeriodType.ANNUAL, period_end=date(fy, 9, 30), fiscal_year=fy
        ),
        provider_info=_prov(f"{symbol}-{metric}-fy{fy}"),
        received_at=_RECEIVED,
    )


def _quarterly(
    symbol: str, metric: str, year: int, q: int, end: date, value: float
) -> FinancialMetric:
    return FinancialMetric(
        symbol=symbol,
        metric=metric,
        value=value,
        period=FinancialPeriod(
            period_type=PeriodType.QUARTERLY,
            period_end=end,
            fiscal_year=year,
            fiscal_quarter=q,
        ),
        provider_info=_prov(f"{symbol}-{metric}-{year}q{q}"),
        received_at=_RECEIVED,
    )


# Deterministic synthetic company "ACME" (ticker ACME) — obviously fictional.
_ACME_ANNUAL = [
    # FY2023..FY2025 revenue / profitability trend
    ("revenue", {2023: 80_000.0, 2024: 96_000.0, 2025: 115_200.0}),
    ("gross_profit", {2023: 36_000.0, 2024: 44_160.0, 2025: 54_000.0}),
    ("operating_income", {2023: 16_000.0, 2024: 21_120.0, 2025: 27_648.0}),
    ("net_income", {2023: 12_800.0, 2024: 17_280.0, 2025: 23_040.0}),
    ("eps_diluted", {2023: 1.28, 2024: 1.72, 2025: 2.28}),
    ("operating_cash_flow", {2023: 18_400.0, 2024: 23_040.0, 2025: 29_952.0}),
    ("capital_expenditure", {2023: 4_000.0, 2024: 4_800.0, 2025: 5_760.0}),
    ("cash_and_equivalents", {2023: 20_000.0, 2024: 24_000.0, 2025: 28_000.0}),
    ("total_debt", {2023: 10_000.0, 2024: 11_000.0, 2025: 12_000.0}),
]

_ACME_QUARTERLY = [
    # FY2025 quarters (fiscal year ends Sep 30)
    ("revenue", {1: 25_600.0, 2: 27_648.0, 3: 29_900.0, 4: 32_052.0}),
    ("net_income", {1: 5_120.0, 2: 5_530.0, 3: 5_982.0, 4: 6_408.0}),
    ("eps_diluted", {1: 0.51, 2: 0.55, 3: 0.59, 4: 0.63}),
]

_Q_ENDS = {1: date(2024, 12, 31), 2: date(2025, 3, 31), 3: date(2025, 6, 30), 4: date(2025, 9, 30)}


def _acme_metrics() -> list[FinancialMetric]:
    out: list[FinancialMetric] = []
    for metric, by_fy in _ACME_ANNUAL:
        for fy, v in by_fy.items():
            out.append(_annual("ACME", metric, fy, v))
    for metric, by_q in _ACME_QUARTERLY:
        for q, v in by_q.items():
            out.append(_quarterly("ACME", metric, 2025, q, _Q_ENDS[q], v))
    return out


class FixtureFundamentalsProvider(FundamentalsProvider):
    """Deterministic fundamentals for the fixture universe."""

    UNIVERSE = {"ACME"}

    def get_company_profile(self, symbol: str) -> CompanyProfile | None:
        if symbol.upper() not in self.UNIVERSE:
            return None
        return CompanyProfile(
            symbol=symbol.upper(),
            name="Acme Industrial Corp (FIXTURE)",
            exchange="NASDAQ",
            sector="Industrials",
            industry="Machinery",
            description=(
                "Synthetic fixture company for M2 development. All figures are "
                "deterministic test data — NOT real financials."
            ),
            employees=42_000,
            currency="USD",
            provider_info=_prov(f"{symbol.lower()}-profile"),
            received_at=_RECEIVED,
        )

    def get_financial_metrics(
        self, symbol: str, period_type: str | None = None, limit: int = 20
    ) -> list[FinancialMetric]:
        if symbol.upper() not in self.UNIVERSE:
            return []
        metrics = _acme_metrics()
        if period_type:
            metrics = [m for m in metrics if m.period.period_type.value == period_type]
        return metrics[:limit]

    def get_statements(
        self, symbol: str, statement_type: str | None = None, limit: int = 8
    ) -> list[FinancialStatement]:
        if symbol.upper() not in self.UNIVERSE:
            return []
        wanted = StatementType(statement_type) if statement_type else None
        out: list[FinancialStatement] = []
        for fy in (2023, 2024, 2025):
            period = FinancialPeriod(
                period_type=PeriodType.ANNUAL, period_end=date(fy, 9, 30), fiscal_year=fy
            )
            rev = dict(_ACME_ANNUAL)["revenue"][fy]
            ni = dict(_ACME_ANNUAL)["net_income"][fy]
            gp = dict(_ACME_ANNUAL)["gross_profit"][fy]
            oi = dict(_ACME_ANNUAL)["operating_income"][fy]
            ocf = dict(_ACME_ANNUAL)["operating_cash_flow"][fy]
            capex = dict(_ACME_ANNUAL)["capital_expenditure"][fy]
            cash = dict(_ACME_ANNUAL)["cash_and_equivalents"][fy]
            debt = dict(_ACME_ANNUAL)["total_debt"][fy]
            statements = [
                FinancialStatement(
                    symbol="ACME",
                    statement_type=StatementType.INCOME,
                    period=period,
                    line_items={
                        "revenue": rev,
                        "gross_profit": gp,
                        "operating_income": oi,
                        "net_income": ni,
                    },
                    provider_info=_prov(f"acme-income-fy{fy}"),
                    received_at=_RECEIVED,
                ),
                FinancialStatement(
                    symbol="ACME",
                    statement_type=StatementType.BALANCE,
                    period=period,
                    line_items={
                        "cash_and_equivalents": cash,
                        "total_debt": debt,
                    },
                    provider_info=_prov(f"acme-balance-fy{fy}"),
                    received_at=_RECEIVED,
                ),
                FinancialStatement(
                    symbol="ACME",
                    statement_type=StatementType.CASHFLOW,
                    period=period,
                    line_items={
                        "operating_cash_flow": ocf,
                        "capital_expenditure": capex,
                    },
                    provider_info=_prov(f"acme-cashflow-fy{fy}"),
                    received_at=_RECEIVED,
                ),
            ]
            out.extend(statements)
        if wanted:
            out = [s for s in out if s.statement_type == wanted]
        return out[:limit]


class FixtureEarningsProvider(EarningsProvider):
    def get_earnings_events(self, symbol: str, limit: int = 12) -> list[EarningsEvent]:
        if symbol.upper() != "ACME":
            return []
        rows = [
            # (event_time, fy, fq, period_end, eps_a, eps_e, rev_a, rev_e)
            (
                datetime(2025, 1, 28, tzinfo=UTC),
                2025,
                1,
                _Q_ENDS[1],
                0.51,
                0.48,
                25_600.0,
                24_800.0,
            ),
            (
                datetime(2025, 4, 29, tzinfo=UTC),
                2025,
                2,
                _Q_ENDS[2],
                0.55,
                0.54,
                27_648.0,
                27_100.0,
            ),
            (
                datetime(2025, 7, 29, tzinfo=UTC),
                2025,
                3,
                _Q_ENDS[3],
                0.59,
                0.60,
                29_900.0,
                30_200.0,
            ),
            (
                datetime(2025, 10, 28, tzinfo=UTC),
                2025,
                4,
                _Q_ENDS[4],
                0.63,
                0.61,
                32_052.0,
                31_500.0,
            ),
        ]
        return [
            EarningsEvent(
                symbol="ACME",
                event_time=t,
                reporting_period=FinancialPeriod(
                    period_type=PeriodType.QUARTERLY,
                    period_end=pe,
                    fiscal_year=fy,
                    fiscal_quarter=fq,
                ),
                eps_actual=a,
                eps_estimate=e,
                revenue_actual=ra,
                revenue_estimate=re_,
                provider_info=_prov(f"acme-earnings-{fy}q{fq}"),
                received_at=_RECEIVED,
            )
            for t, fy, fq, pe, a, e, ra, re_ in rows
        ][:limit]


class FixtureValuationProvider(ValuationProvider):
    def get_valuation_snapshot(self, symbol: str) -> ValuationSnapshot | None:
        if symbol.upper() != "ACME":
            return None
        return ValuationSnapshot(
            symbol="ACME",
            as_of=_RECEIVED,
            price=91.20,
            market_cap=912_000.0,
            pe_ratio=39.58,
            ps_ratio=7.92,
            shares_outstanding=10_000.0,
            currency="USD",
            provider_info=_prov("acme-valuation"),
            received_at=_RECEIVED,
        )


class FixtureDocumentsProvider(FinancialDocumentsProvider):
    DOCS = [
        (
            "acme-fy2025-10k",
            "ACME FY2025 Annual Report (FIXTURE)",
            DocumentType.FILING,
            "https://example.invalid/acme/fy2025-10k",
            date(2025, 11, 15),
            "Synthetic annual report. Revenue grew 20% YoY to $115.2B; net margin "
            "expanded to 20%. Management guides to continued double-digit growth.",
        ),
        (
            "acme-q4-2025-release",
            "ACME Q4 FY2025 Earnings Release (FIXTURE)",
            DocumentType.EARNINGS_RELEASE,
            "https://example.invalid/acme/q4-2025",
            date(2025, 10, 28),
            "Synthetic release. Q4 EPS $0.63 vs $0.61 consensus; revenue $32.05B "
            "beat estimates. Backlog up 14% YoY.",
        ),
        (
            "acme-supply-note",
            "ACME supplier concentration note (FIXTURE)",
            DocumentType.ANNOUNCEMENT,
            "https://example.invalid/acme/supply",
            date(2025, 12, 2),
            "Synthetic announcement. Two suppliers account for 35% of component "
            "sourcing; diversification planned through FY2027.",
        ),
    ]

    def get_documents(self, symbol: str, since=None, limit: int = 25):
        if symbol.upper() != "ACME":
            return []
        docs = [
            ResearchDocument(
                document_id=doc_id,
                symbol="ACME",
                title=title,
                document_type=dtype,
                source="fixture_ir",
                url=url,
                published_at=datetime.combine(pub, datetime.min.time(), tzinfo=UTC),
                retrieved_at=_RECEIVED,
                content=content,
                provider_info=_prov(doc_id),
            )
            for doc_id, title, dtype, url, pub, content in self.DOCS
        ]
        if since is not None:
            docs = [d for d in docs if d.published_at.date() >= since]
        return docs[:limit]
