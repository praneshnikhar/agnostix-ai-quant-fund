"""M2.2 operational evaluation-runner tests.

Deterministic, fully mocked: no live LLM/provider/network calls. Covers the
identical-context invariant, failure isolation, metric fidelity (tokens/cost
never fabricated), deterministic ordering, report comparison, and the
research-only permission boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fundamentals.context import build_fundamental_context
from fundamentals.providers.fixture import FixtureFundamentalsProvider
from fundamentals.research.evaluation import (
    CONTEXT_VERSION,
    EvaluationInvariantError,
    EvaluationRecord,
    ModelTarget,
    _verify_same_context,
    run_evaluation,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


# ------------------------------------------------------------------ helpers


def _emitter():
    from agents.events import EventSinkRegistry, RegistryEmitter

    return RegistryEmitter(EventSinkRegistry())


def _ctx():
    fp = FixtureFundamentalsProvider()
    return build_fundamental_context(
        "ACME",
        profile=fp.get_company_profile("ACME"),
        metrics=fp.get_financial_metrics("ACME"),
        now=NOW,
    )


def _thesis_payload(
    *,
    view: str = "NEUTRAL",
    confidence: float = 0.5,
    fact: str | None = None,
    evidence_source: str | None = None,
) -> dict:
    """A structurally valid thesis; optionally carrying one FACT statement."""
    statements = []
    if fact is not None:
        statements.append({"kind": "FACT", "text": fact, "evidence_ids": ["ev1"]})
    payload = {
        "symbol": "ACME",
        "research_timestamp": NOW.isoformat(),
        "fundamental_view": view,
        "confidence": confidence,
        "investment_thesis": "Evaluation harness probe.",
        "financial_assessment": {"area": "financial", "summary": "ok"},
        "growth_assessment": {"area": "growth", "summary": "ok"},
        "profitability_assessment": {"area": "profitability", "summary": "ok"},
        "cash_flow_assessment": {"area": "cash_flow", "summary": "ok"},
        "balance_sheet_assessment": {"area": "balance_sheet", "summary": "ok"},
        "valuation_assessment": {"area": "valuation", "summary": "ok"},
        "evidence": [],
    }
    if statements:
        payload["growth_assessment"]["statements"] = statements  # type: ignore[index]
    if evidence_source is not None:
        payload["evidence"] = [
            {
                "evidence_id": "ev1",
                "source": evidence_source,
                "source_type": "document",
                "claim_supported": "probe",
            }
        ]
    return payload


class _MockGateway:
    """Deterministic mocked gateway — no live LLM."""

    class ModelClass:
        REASONING = "reasoning"

    def __init__(self, payload: dict, *, usage: dict | None = None, model: str = "mock-model-1"):
        self._payload = payload
        self._usage = usage
        self._model = model
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "content": None,
            "structured": self._payload,
            "provider": "mock",
            "model": self._model,
            "latency_ms": 7,
            "usage": self._usage,
        }


class _ExplodingGateway(_MockGateway):
    async def run(self, **kwargs):
        raise RuntimeError("provider outage")


def _targets(*pairs: tuple[str, str]) -> list[ModelTarget]:
    return [ModelTarget(provider=p, model=m) for p, m in pairs]


def _factory(gateways: dict[tuple[str, str], object]):
    def make(target: ModelTarget):
        gw = gateways.get((target.provider, target.model))
        if gw is None:
            raise ValueError(f"provider {target.provider!r} not configured")
        return gw

    return make


async def _run(targets, gateways, *, context_builder=None, context=None):
    """Run with an explicit context/builder, or a fresh default context."""
    kwargs: dict = {"emitter": _emitter(), "gateway_factory": _factory(gateways)}
    if context is not None:
        kwargs["context"] = context
    elif context_builder is not None:
        kwargs["context_builder"] = context_builder
    else:
        kwargs["context"] = _ctx()
    return await run_evaluation("ACME", targets, **kwargs)


# ------------------------------------------------------------------- tests


@pytest.mark.anyio
async def test_context_built_exactly_once():
    calls: list[str] = []

    async def builder(symbol: str):
        calls.append(symbol)
        return _ctx()

    good = _MockGateway(_thesis_payload())
    result = await _run(
        _targets(("p1", "m1"), ("p2", "m2"), ("p3", "m3")),
        {("p1", "m1"): good, ("p2", "m2"): good, ("p3", "m3"): good},
        context_builder=builder,
    )
    assert calls == ["ACME"]  # ONE build for ALL models
    assert len(result.records) == 3


@pytest.mark.anyio
async def test_all_records_share_context_version_and_hash():
    ctx = _ctx()
    gateways = {
        ("a", "m-a"): _MockGateway(_thesis_payload()),
        ("b", "m-b"): _MockGateway(_thesis_payload()),
    }
    result = await _run(_targets(("a", "m-a"), ("b", "m-b")), gateways, context=ctx)
    assert result.context_version == CONTEXT_VERSION == "m2-v2"
    assert result.context_hash == ctx.context_hash
    for r in result.records:
        assert r.context_version == ctx.context_version
        assert r.context_hash == ctx.context_hash


@pytest.mark.anyio
async def test_models_execute_independently():
    g1 = _MockGateway(_thesis_payload())
    g2 = _MockGateway(_thesis_payload())
    await _run(_targets(("p1", "m1"), ("p2", "m2")), {("p1", "m1"): g1, ("p2", "m2"): g2})
    assert len(g1.calls) == 1
    assert len(g2.calls) == 1
    # Same prompt version delivered to every model.
    assert g1.calls[0]["prompt_version"] == g2.calls[0]["prompt_version"]


@pytest.mark.anyio
async def test_one_model_failure_does_not_stop_others():
    ok1 = _MockGateway(_thesis_payload())
    boom = _ExplodingGateway(_thesis_payload())
    ok2 = _MockGateway(_thesis_payload())
    result = await _run(
        _targets(("p1", "m1"), ("p2", "boom"), ("p3", "m3")),
        {("p1", "m1"): ok1, ("p2", "boom"): boom, ("p3", "m3"): ok2},
    )
    statuses = [(r.provider, r.status) for r in result.records]
    assert statuses == [("p1", "completed"), ("p2", "failed"), ("p3", "completed")]
    failed = result.records[1]
    assert failed.error is not None and "outage" in failed.error
    # A failed model gets NO fabricated research output.
    assert failed.fundamental_view is None
    assert failed.critic_verdict is None
    assert failed.schema_valid is False


@pytest.mark.anyio
async def test_gateway_factory_failure_isolated():
    ok = _MockGateway(_thesis_payload())
    result = await _run(
        _targets(("ghost", "m-x"), ("real", "m-y")),
        {("real", "m-y"): ok},
    )
    assert result.records[0].status == "failed"
    assert "gateway unavailable" in (result.records[0].error or "")
    assert result.records[1].status == "completed"


@pytest.mark.anyio
async def test_structured_output_failure_recorded():
    garbage = _MockGateway({"structured": {"garbage": True}})
    result = await _run(_targets(("p", "m")), {("p", "m"): garbage})
    r = result.records[0]
    assert r.status == "failed"
    assert r.success is False
    assert r.schema_valid is False
    assert r.error is not None


@pytest.mark.anyio
async def test_critic_and_grounding_results_recorded():
    gw = _MockGateway(_thesis_payload())
    result = await _run(_targets(("p", "m")), {("p", "m"): gw})
    r = result.records[0]
    assert r.critic_verdict is not None and r.critic_verdict.value == "PASS"
    assert r.grounding_passed is True
    assert r.unsupported_claims == 0 and r.contradicted_claims == 0


@pytest.mark.anyio
async def test_hallucinated_fact_fails_grounding():
    gw = _MockGateway(_thesis_payload(fact="Revenue was 999,999.0 in FY2025."))
    result = await _run(_targets(("p", "m")), {("p", "m"): gw})
    r = result.records[0]
    assert r.grounding_passed is False
    assert r.contradicted_claims >= 1


@pytest.mark.anyio
async def test_token_metadata_preserved_when_supplied():
    usage = {
        "prompt_tokens": 1200,
        "completion_tokens": 340,
        "total_tokens": 1540,
        "estimated_cost_usd": 0.0123,
    }
    gw = _MockGateway(_thesis_payload(), usage=usage)
    result = await _run(_targets(("p", "m")), {("p", "m"): gw})
    r = result.records[0]
    assert r.input_tokens == 1200
    assert r.output_tokens == 340
    assert r.total_tokens == 1540
    assert r.estimated_cost_usd == pytest.approx(0.0123)


@pytest.mark.anyio
async def test_missing_token_metadata_stays_unavailable():
    gw = _MockGateway(_thesis_payload(), usage=None)
    result = await _run(_targets(("p", "m")), {("p", "m"): gw})
    r = result.records[0]
    assert r.input_tokens is None
    assert r.output_tokens is None
    assert r.total_tokens is None
    assert r.estimated_cost_usd is None


@pytest.mark.anyio
async def test_cost_never_fabricated_when_provider_omits_it():
    # Tokens reported but no price metadata: cost must remain None, never 0.
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    gw = _MockGateway(_thesis_payload(), usage=usage)
    result = await _run(_targets(("p", "m")), {("p", "m"): gw})
    assert result.records[0].estimated_cost_usd is None


@pytest.mark.anyio
async def test_model_version_records_provider_reported_id():
    gw = _MockGateway(_thesis_payload(), model="served-id-2026-08")
    result = await _run(_targets(("p", "requested-alias")), {("p", "requested-alias"): gw})
    r = result.records[0]
    assert r.model == "requested-alias"  # configured identity
    assert r.model_version == "served-id-2026-08"  # what actually served


@pytest.mark.anyio
async def test_data_quality_limitations_recorded():
    gw = _MockGateway(_thesis_payload())
    result = await _run(_targets(("p", "m")), {("p", "m"): gw})
    r = result.records[0]
    # The minimal context lacks earnings/valuation/docs/news/snapshot.
    assert "earnings" in r.data_gaps
    assert "market_snapshot" in r.data_gaps
    assert result.unavailable == r.data_gaps


@pytest.mark.anyio
async def test_evaluation_ordering_deterministic():
    gateways = {
        ("p3", "m3"): _MockGateway(_thesis_payload()),
        ("p1", "m1"): _MockGateway(_thesis_payload()),
        ("p2", "m2"): _MockGateway(_thesis_payload()),
    }
    targets = _targets(("p3", "m3"), ("p1", "m1"), ("p2", "m2"))
    first = await _run(targets, gateways)
    second = await _run(targets, gateways)
    order_a = [(r.provider, r.model) for r in first.records]
    order_b = [(r.provider, r.model) for r in second.records]
    assert order_a == order_b == [("p3", "m3"), ("p1", "m1"), ("p2", "m2")]
    # Serialization stable apart from wall-clock provenance fields.
    strip = lambda rs: [  # noqa: E731
        r.model_dump(mode="json", exclude={"run_timestamp", "latency_ms"}) for r in rs
    ]
    assert strip(first.records) == strip(second.records)


@pytest.mark.anyio
async def test_report_compares_models():
    gateways = {
        ("alpha", "big"): _MockGateway(_thesis_payload(), usage={"total_tokens": 100}),
        ("beta", "small"): _MockGateway(_thesis_payload(), usage={"total_tokens": 40}),
        ("gamma", "dead"): _ExplodingGateway(_thesis_payload()),
    }
    result = await _run(
        _targets(("alpha", "big"), ("beta", "small"), ("gamma", "dead")), gateways
    )
    summary = result.summary()
    assert set(summary) == {"alpha/big", "beta/small", "gamma/dead"}
    assert summary["alpha/big"]["critic_pass"] == 1
    assert summary["beta/small"]["schema_valid"] == 1
    assert summary["gamma/dead"]["failed"] == 1
    assert summary["gamma/dead"]["success"] == 0


@pytest.mark.anyio
async def test_identical_context_invariant_fails_run_on_mismatch():
    ctx = _ctx()
    rogue = EvaluationRecord(
        provider="rogue",
        model="m",
        context_version="other-version",
        context_hash="deadbeef",
        symbol="ACME",
    )
    with pytest.raises(EvaluationInvariantError):
        _verify_same_context(rogue, ctx)


@pytest.mark.anyio
async def test_wrong_context_version_fails_run():
    from fundamentals.context import FundamentalResearchContext

    stale = _ctx().model_copy(update={"context_version": "v0"})
    assert isinstance(stale, FundamentalResearchContext)
    with pytest.raises(EvaluationInvariantError):
        await _run(
            _targets(("p", "m")),
            {("p", "m"): _MockGateway(_thesis_payload())},
            context=stale,
        )


@pytest.mark.anyio
async def test_runner_input_validation():
    with pytest.raises(ValueError):
        await run_evaluation(
            "ACME", [], emitter=None, context=_ctx(), gateway_factory=lambda t: None
        )
    with pytest.raises(ValueError):
        await run_evaluation(
            "ACME",
            _targets(("p", "m")),
            emitter=None,
            gateway_factory=lambda t: None,
        )  # neither context nor builder
    async def _builder(symbol: str):
        return _ctx()

    with pytest.raises(ValueError):
        await run_evaluation(
            "ACME",
            _targets(("p", "m")),
            emitter=None,
            context=_ctx(),
            context_builder=_builder,
            gateway_factory=lambda t: None,
        )


@pytest.mark.anyio
async def test_no_trading_permissions_introduced():
    from agents.contracts import ToolPermission
    from fundamentals.research.agent import FundamentalResearchAgent

    agent = FundamentalResearchAgent(_MockGateway(_thesis_payload()), _emitter())
    assert agent.spec.tool_permissions <= {
        ToolPermission.READ_MARKET_DATA,
        ToolPermission.READ_NEWS,
        ToolPermission.READ_SNAPSHOT,
        ToolPermission.VERIFY_EVIDENCE,
    }
    assert ToolPermission.PLACE_ORDER not in agent.spec.tool_permissions
    assert ToolPermission.SUBMIT_PROPOSAL not in agent.spec.tool_permissions
    assert ToolPermission.EVALUATE_RISK_RULES not in agent.spec.tool_permissions
