"""M2 fundamentals service tests — deterministic, no live providers."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from fundamentals.context import (
    build_fundamental_context,
    render_context_for_model,
)
from fundamentals.metrics import earnings_surprise, margin, net_debt, revenue_growth_yoy
from fundamentals.providers.fixture import (
    FixtureDocumentsProvider,
    FixtureEarningsProvider,
    FixtureFundamentalsProvider,
    FixtureValuationProvider,
)
from fundamentals.research.agent import FundamentalResearchAgent
from fundamentals.research.critic import CriticInput, FundamentalResearchCritic
from fundamentals.research.grounding import run_deterministic_checks
from fundamentals.research.schemas import (
    Assessment,
    ClaimCheckStatus,
    ClaimKind,
    EvidenceRef,
    FundamentalView,
    InvestmentThesis,
    ResearchStatement,
    Verdict,
)
from fundamentals.schemas import (
    DataQuality,
    EarningsResult,
    FinancialMetric,
    FinancialPeriod,
    PeriodType,
    ProviderInfo,
)
from fundamentals.validation import flag_quality, validate_metrics

NOW = datetime(2026, 8, 1, tzinfo=UTC)
PROV = ProviderInfo(provider="fixture", raw_record_id="r1")


def _emitter():
    from agents.events import EventSinkRegistry, RegistryEmitter

    return RegistryEmitter(EventSinkRegistry())


def _metric(metric: str, value: float | None, end: date, pt=PeriodType.ANNUAL, fy=2025, fq=None):
    return FinancialMetric(
        symbol="ACME",
        metric=metric,
        value=value,
        period=FinancialPeriod(period_type=pt, period_end=end, fiscal_year=fy, fiscal_quarter=fq),
        provider_info=PROV,
        received_at=NOW,
    )


# ---------------------------------------------------------------- schemas


def test_quarterly_period_requires_fiscal_quarter():
    with pytest.raises(ValidationError):
        FinancialPeriod(period_type=PeriodType.QUARTERLY, period_end=date(2025, 3, 31))


def test_annual_period_requires_fiscal_year():
    with pytest.raises(ValidationError):
        FinancialPeriod(period_type=PeriodType.ANNUAL, period_end=date(2025, 9, 30))


def test_naive_timestamp_rejected():
    with pytest.raises(ValidationError):
        FinancialMetric.model_validate(
            _metric("revenue", 100.0, date(2025, 9, 30)).model_dump(mode="json")
            | {"received_at": "2026-01-01T00:00:00"}
        )


def test_symbol_uppercased():
    assert _metric("revenue", 1.0, date(2025, 9, 30)).symbol == "ACME"


# ------------------------------------------------------------- validation


def test_negative_revenue_flagged_invalid():
    flagged = flag_quality([_metric("revenue", -5.0, date(2025, 9, 30))])
    assert flagged[0].quality == DataQuality.INVALID
    assert flagged[0].value == -5.0  # never corrected


def test_conflicting_sources_flagged_not_merged():
    a = _metric("revenue", 100.0, date(2025, 9, 30))
    b = _metric("revenue", 250.0, date(2025, 9, 30))
    flagged = flag_quality([a, b])
    assert all(m.quality == DataQuality.CONFLICTING for m in flagged)
    assert {m.value for m in flagged} == {100.0, 250.0}


def test_ttm_with_fiscal_ids_flagged():
    m = _metric("revenue", 100.0, date(2025, 9, 30), pt=PeriodType.TTM, fy=2025)
    issues = validate_metrics([m])
    assert any(i.issue == "ttm_with_fiscal_ids" for lst in issues.values() for i in lst)


def test_none_value_is_valid_unavailability():
    assert validate_metrics([_metric("revenue", None, date(2025, 9, 30))]) == {}


# ---------------------------------------------------------------- metrics


def test_revenue_growth_yoy_deterministic():
    metrics = [
        _metric("revenue", 115_200.0, date(2025, 9, 30)),
        _metric("revenue", 96_000.0, date(2024, 9, 30)),
    ]
    d = revenue_growth_yoy(metrics, date(2025, 9, 30), date(2024, 9, 30))
    assert d is not None and d.value == pytest.approx(0.2)
    assert d.formula and len(d.inputs) == 2


def test_margin_missing_inputs_returns_none():
    assert (
        margin(
            [_metric("gross_profit", 10.0, date(2025, 9, 30))], "gross_profit", date(2025, 9, 30)
        )
        is None
    )


def test_net_debt_and_surprise():
    metrics = [
        _metric("total_debt", 12_000.0, date(2025, 9, 30), pt=PeriodType.QUARTERLY, fy=2025, fq=4),
        _metric(
            "cash_and_equivalents",
            28_000.0,
            date(2025, 9, 30),
            pt=PeriodType.QUARTERLY,
            fy=2025,
            fq=4,
        ),
    ]
    nd = net_debt(metrics, date(2025, 9, 30), PeriodType.QUARTERLY)
    assert nd is not None and nd.value == -16_000.0
    assert earnings_surprise(0.63, 0.61) == (pytest.approx(0.02), pytest.approx(0.032787, rel=1e-4))
    assert earnings_surprise(None, 0.61) == (None, None)


# --------------------------------------------------------------- fixtures


def test_fixture_providers_deterministic():
    p = FixtureFundamentalsProvider()
    m1 = p.get_financial_metrics("ACME")
    m2 = p.get_financial_metrics("ACME")
    assert [x.model_dump() for x in m1] == [x.model_dump() for x in m2]
    assert p.get_company_profile("NOPE") is None
    prof = p.get_company_profile("acme")
    assert prof is not None and prof.symbol == "ACME"
    assert FixtureEarningsProvider().get_earnings_events("ACME")
    val = FixtureValuationProvider().get_valuation_snapshot("ACME")
    assert val is not None and val.price == 91.20
    assert len(FixtureDocumentsProvider().get_documents("ACME")) == 3


# ---------------------------------------------------------------- context


def _full_context():
    fp = FixtureFundamentalsProvider()
    ep = FixtureEarningsProvider()
    vp = FixtureValuationProvider()
    dp = FixtureDocumentsProvider()
    metrics = fp.get_financial_metrics("ACME")
    earnings = []
    for e in ep.get_earnings_events("ACME"):
        s, p = earnings_surprise(e.eps_actual, e.eps_estimate)
        earnings.append(EarningsResult(event=e, eps_surprise=s, eps_surprise_pct=p))
    return build_fundamental_context(
        "ACME",
        profile=fp.get_company_profile("ACME"),
        metrics=metrics,
        earnings=earnings,
        valuation=vp.get_valuation_snapshot("ACME"),
        documents=dp.get_documents("ACME"),
        now=NOW,
    )


def test_context_deterministic_and_hashed():
    c1, c2 = _full_context(), _full_context()
    assert c1.context_hash == c2.context_hash
    assert c1.context_hash and not c1.unavailable


def test_context_budget_limits():
    ctx = _full_context()
    assert len(ctx.documents) <= 5
    assert len(ctx.earnings) <= 4


def test_context_records_gaps():
    ctx = build_fundamental_context("ACME", profile=None, metrics=[], now=NOW)
    assert "company_profile" in ctx.unavailable
    assert "financial_metrics" in ctx.unavailable
    assert "earnings" in ctx.unavailable


def test_rendered_context_labels_unavailable():
    ctx = build_fundamental_context("ACME", profile=None, metrics=[], now=NOW)
    text = render_context_for_model(ctx)
    assert "unavailable" in text
    assert "do NOT invent" in text


# --------------------------------------------------------------- thesis


def _thesis(view=FundamentalView.BULLISH, confidence=0.7, fact="Revenue was 115,200.0 in FY2025."):
    return InvestmentThesis(
        symbol="ACME",
        research_timestamp=NOW,
        fundamental_view=view,
        confidence=confidence,
        investment_thesis="Strong growth.",
        financial_assessment=Assessment(area="financial", summary="ok"),
        growth_assessment=Assessment(
            area="growth",
            summary="growing",
            statements=[ResearchStatement(kind=ClaimKind.FACT, text=fact, evidence_ids=["ev1"])],
        ),
        profitability_assessment=Assessment(area="profitability", summary="ok"),
        cash_flow_assessment=Assessment(area="cash_flow", summary="ok"),
        balance_sheet_assessment=Assessment(area="balance_sheet", summary="ok"),
        valuation_assessment=Assessment(area="valuation", summary="ok"),
        evidence=[
            EvidenceRef(
                evidence_id="ev1",
                source="acme-fy2025-10k",
                source_type="document",
                claim_supported="growth",
            )
        ],
    )


# -------------------------------------------------------------- grounding


def test_grounded_fact_passes():
    ctx = _full_context()
    det = run_deterministic_checks(_thesis(), ctx)
    assert det["passed"], det["findings"]


def test_hallucinated_number_contradicted():
    ctx = _full_context()
    det = run_deterministic_checks(_thesis(fact="Revenue was 999,999.0 in FY2025."), ctx)
    assert not det["passed"]
    assert det["contradicted_count"] >= 1


def test_invented_evidence_source_unsupported():
    ctx = _full_context()
    thesis = _thesis()
    thesis.evidence[0].source = "not-a-real-doc"
    det = run_deterministic_checks(thesis, ctx)
    assert not det["passed"]
    assert any(c["status"] == ClaimCheckStatus.UNSUPPORTED.value for c in det["claim_checks"])


# ----------------------------------------------------------------- critic


@pytest.mark.anyio
async def test_critic_passes_grounded_thesis():
    ctx = _full_context()
    critic = FundamentalResearchCritic(_emitter())
    result = await critic.run(CriticInput(context=ctx, thesis=_thesis()))
    assert result.review.verdict == Verdict.PASS
    assert result.review.deterministic_checks_passed


@pytest.mark.anyio
async def test_critic_rejects_hallucinated_numbers():
    ctx = _full_context()
    critic = FundamentalResearchCritic(_emitter())
    result = await critic.run(
        CriticInput(context=ctx, thesis=_thesis(fact="Revenue was 42.0 in FY2025."))
    )
    assert result.review.verdict in {Verdict.REVISE, Verdict.REJECT}


@pytest.mark.anyio
async def test_critic_requires_insufficient_data_view_without_metrics():
    ctx = build_fundamental_context("ACME", profile=None, metrics=[], now=NOW)
    critic = FundamentalResearchCritic(_emitter())
    result = await critic.run(CriticInput(context=ctx, thesis=_thesis()))
    assert result.review.verdict in {Verdict.REVISE, Verdict.REJECT}


# ------------------------------------------------------- agent + harness


class _MockGateway:
    """Deterministic mocked gateway — no live LLM in tests."""

    class ModelClass:
        REASONING = "reasoning"

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "content": None,
            "structured": self._payload,
            "provider": "mock",
            "model": "mock-model-1",
            "latency_ms": 12,
        }


def _mock_thesis_payload():
    t = _thesis()
    return t.model_dump(mode="json")


@pytest.mark.anyio
async def test_agent_produces_valid_thesis_via_mock_gateway():
    ctx = _full_context()
    gw = _MockGateway(_mock_thesis_payload())
    agent = FundamentalResearchAgent(gw, _emitter())
    result = await agent.run(ctx)
    assert result.thesis.symbol == "ACME"
    assert result.provider == "mock"
    assert result.context_hash == ctx.context_hash
    assert gw.calls[0]["prompt_version"] == "m2-fundamental-v1"
    assert "115,200.0" in gw.calls[0]["messages"][1]["content"]


@pytest.mark.anyio
async def test_agent_rejects_non_context_input():
    agent = FundamentalResearchAgent(_MockGateway({}), _emitter())
    with pytest.raises(TypeError):
        await agent.run("not a context")  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_agent_fails_on_unparseable_output():
    ctx = _full_context()
    gw = _MockGateway({"structured": {"garbage": True}})
    agent = FundamentalResearchAgent(gw, _emitter())
    with pytest.raises(ValueError):
        await agent.run(ctx)


@pytest.mark.anyio
async def test_evaluation_harness_records_and_summarizes():
    from fundamentals.research.evaluation import evaluate_model

    ctx = _full_context()
    rec = await evaluate_model(
        _MockGateway(_mock_thesis_payload()),
        _emitter(),
        ctx,
        provider_label="mock",
        model_label="mock-model-1",
    )
    assert rec.success and rec.schema_valid
    assert rec.critic_verdict == Verdict.PASS
    from fundamentals.research.evaluation import EvaluationReport

    summary = EvaluationReport(records=[rec]).summary()
    assert summary["mock/mock-model-1"]["critic_pass"] == 1


# ------------------------------------------------------------- permissions


def test_agent_has_no_execution_permissions():
    from agents.contracts import ToolPermission

    agent = FundamentalResearchAgent(_MockGateway({}), _emitter())
    perms = agent.spec.tool_permissions
    assert ToolPermission.PLACE_ORDER not in perms
    # least privilege: only read/verify permissions granted (§28)
    assert perms <= {
        ToolPermission.READ_MARKET_DATA,
        ToolPermission.READ_NEWS,
        ToolPermission.READ_SNAPSHOT,
        ToolPermission.VERIFY_EVIDENCE,
    }
