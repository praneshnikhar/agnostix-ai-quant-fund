"""Model evaluation harness (M2, .clinerules §21/§22).

Operational multi-model runner (M2.2): ONE immutable research context is
built exactly once (via an injected builder or supplied directly), then
every configured provider/model target is evaluated against that exact
context through the Model Gateway seam, followed by deterministic grounding
and the FundamentalResearchCritic per model.

Guarantees:
- identical-context: every record must reference the run's single
  context_version + context_hash; any mismatch fails the whole run rather
  than silently comparing different contexts.
- failure isolation: one model failing never blocks the others — its record
  is marked status="failed" with structured error metadata and NO fabricated
  research output.
- determinism: targets are evaluated strictly in configuration order and
  records are returned in that same order.
- no fabrication: token/cost fields stay None when a provider does not
  report them (.clinerules §33).

Normal CI uses mocked gateways only — never live LLM calls.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from fundamentals.context import CONTEXT_VERSION, FundamentalResearchContext
from fundamentals.research.agent import PROMPT_VERSION as AGENT_PROMPT_VERSION
from fundamentals.research.agent import FundamentalResearchAgent
from fundamentals.research.critic import CriticInput, FundamentalResearchCritic
from fundamentals.research.grounding import run_deterministic_checks
from fundamentals.research.schemas import ClaimCheckStatus, Verdict

# Agent identity recorded on persisted evaluation runs (§23 provenance).
EVALUATION_AGENT_ID = "fundamental_research_agent"
EVALUATION_AGENT_VERSION = "v1"


class ModelTarget(BaseModel):
    """One configured provider/model combination to evaluate.

    `provider`/`model` are free-form strings so any current or future
    gateway provider (anthropic/openai/ollama/openrouter/...) is expressible
    without code changes here.
    """

    provider: str
    model: str


class EvaluationRecord(BaseModel):
    provider: str
    model: str
    task: str = "fundamental_analysis"
    prompt_version: str = AGENT_PROMPT_VERSION
    context_version: str = ""
    context_hash: str
    symbol: str
    status: str = "completed"  # completed | failed
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    success: bool = False
    schema_valid: bool = False
    error: str | None = None
    fundamental_view: str | None = None
    confidence: float | None = None
    critic_verdict: Verdict | None = None
    grounding_passed: bool | None = None
    unsupported_claims: int = 0
    contradicted_claims: int = 0
    evidence_coverage: float | None = None
    data_gaps: list[str] = Field(default_factory=list)
    # Model id as reported by the PROVIDER response — may differ from the
    # requested alias; recorded for honest provenance, never assumed equal.
    model_version: str | None = None
    run_timestamp: datetime | None = None


class EvaluationReport(BaseModel):
    records: list[EvaluationRecord] = Field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """Reliability-first comparison (§22): grounding & schema validity
        outrank prose quality."""
        by_model: dict[str, dict[str, Any]] = {}
        for r in self.records:
            key = f"{r.provider}/{r.model}"
            s = by_model.setdefault(
                key,
                {
                    "runs": 0,
                    "completed": 0,
                    "failed": 0,
                    "success": 0,
                    "schema_valid": 0,
                    "critic_pass": 0,
                    "grounding_passed": 0,
                    "unsupported_claims": 0,
                    "contradicted_claims": 0,
                    "total_latency_ms": 0,
                    "total_cost_usd": 0.0,
                },
            )
            s["runs"] += 1
            s["completed"] += int(r.status == "completed")
            s["failed"] += int(r.status == "failed")
            s["success"] += int(r.success)
            s["schema_valid"] += int(r.schema_valid)
            s["critic_pass"] += int(r.critic_verdict == Verdict.PASS)
            s["grounding_passed"] += int(r.grounding_passed is True)
            s["unsupported_claims"] += r.unsupported_claims
            s["contradicted_claims"] += r.contradicted_claims
            s["total_latency_ms"] += r.latency_ms
            s["total_cost_usd"] += r.estimated_cost_usd or 0.0
        return by_model


class EvaluationRunResult(BaseModel):
    """Comparable outcome of one multi-model evaluation over ONE context."""

    symbol: str
    context_version: str
    context_hash: str
    unavailable: list[str] = Field(default_factory=list)  # data-quality limitations
    records: list[EvaluationRecord] = Field(default_factory=list)

    def report(self) -> EvaluationReport:
        return EvaluationReport(records=self.records)

    def summary(self) -> dict[str, Any]:
        return self.report().summary()


class EvaluationInvariantError(RuntimeError):
    """Raised when an evaluation would compare different contexts."""


# A builder receives the symbol and returns the research context. It MUST be
# deterministic and MUST be invoked at most once per evaluation run.
ContextBuilder = Callable[[str], Awaitable[FundamentalResearchContext]]
# A factory materializes a gateway bound to one configured target. It may
# raise when a provider is unavailable — that fails ONLY that model's record.
GatewayFactory = Callable[[ModelTarget], object]


async def evaluate_model(
    gateway,
    emitter,
    ctx: FundamentalResearchContext,
    *,
    provider_label: str,
    model_label: str,
) -> EvaluationRecord:
    """Run one full agent+grounding+critic cycle against one gateway."""
    record = EvaluationRecord(
        provider=provider_label,
        model=model_label,
        context_version=ctx.context_version,
        context_hash=ctx.context_hash,
        symbol=ctx.symbol,
        data_gaps=list(ctx.unavailable),
        run_timestamp=datetime.now(UTC),
    )
    agent = FundamentalResearchAgent(gateway, emitter)
    start = time.perf_counter()
    try:
        run_result = await agent.run(ctx)
        record.latency_ms = run_result.latency_ms or int((time.perf_counter() - start) * 1000)
        record.success = True
        record.schema_valid = True
        record.fundamental_view = run_result.thesis.fundamental_view.value
        record.confidence = run_result.thesis.confidence
        record.model_version = run_result.model or None
        record.input_tokens = run_result.input_tokens
        record.output_tokens = run_result.output_tokens
        record.total_tokens = run_result.total_tokens
        record.estimated_cost_usd = run_result.estimated_cost_usd

        det = run_deterministic_checks(run_result.thesis, ctx)
        record.grounding_passed = bool(det["passed"])
        record.unsupported_claims = int(det["unsupported_count"])
        record.contradicted_claims = int(det["contradicted_count"])
        record.evidence_coverage = _evidence_coverage(det["claim_checks"])

        critic = FundamentalResearchCritic(emitter)
        critic_out = await critic.run(CriticInput(context=ctx, thesis=run_result.thesis))
        record.critic_verdict = critic_out.review.verdict
    except Exception as exc:
        record.status = "failed"
        record.success = False
        record.error = repr(exc)[:500]
        record.latency_ms = int((time.perf_counter() - start) * 1000)
    return record


async def run_evaluation(
    symbol: str,
    targets: Sequence[ModelTarget],
    *,
    emitter,
    context: FundamentalResearchContext | None = None,
    context_builder: ContextBuilder | None = None,
    gateway_factory: GatewayFactory,
) -> EvaluationRunResult:
    """Evaluate every configured model against ONE shared context.

    Exactly one of `context` / `context_builder` must be supplied; either
    way the context exists exactly once for the whole run. Targets are
    processed in configuration order; per-model failures are isolated into
    their records. If the context cannot be produced, or any record would
    reference a different context, the run FAILS loudly.
    """
    if not targets:
        raise ValueError("run_evaluation requires at least one model target")
    if (context is None) == (context_builder is None):
        raise ValueError("run_evaluation requires exactly one of context or context_builder")

    if context is None:
        if context_builder is None:  # unreachable: guarded by validation above
            raise ValueError("context_builder required when context is absent")
        ctx = await context_builder(symbol)  # built EXACTLY once
    else:
        ctx = context

    if ctx.context_version != CONTEXT_VERSION:
        raise EvaluationInvariantError(
            f"context version {ctx.context_version!r} != expected {CONTEXT_VERSION!r}"
        )

    records: list[EvaluationRecord] = []
    for target in targets:
        try:
            gateway = gateway_factory(target)
        except Exception as exc:
            records.append(_failed_record(target, ctx, f"gateway unavailable: {exc!r}"))
            await _emit_model_event(emitter, ctx, target, status="failed", error=records[-1].error)
            continue
        record = await evaluate_model(
            gateway,
            emitter,
            ctx,
            provider_label=target.provider,
            model_label=target.model,
        )
        _verify_same_context(record, ctx)
        records.append(record)
        await _emit_model_event(emitter, ctx, target, status=record.status)

    return EvaluationRunResult(
        symbol=ctx.symbol,
        context_version=ctx.context_version,
        context_hash=ctx.context_hash,
        unavailable=list(ctx.unavailable),
        records=records,
    )


def _failed_record(target: ModelTarget, ctx: FundamentalResearchContext, error: str):
    return EvaluationRecord(
        provider=target.provider,
        model=target.model,
        context_version=ctx.context_version,
        context_hash=ctx.context_hash,
        symbol=ctx.symbol,
        status="failed",
        success=False,
        schema_valid=False,
        error=error[:500],
        data_gaps=list(ctx.unavailable),
        run_timestamp=datetime.now(UTC),
    )


def _verify_same_context(record: EvaluationRecord, ctx: FundamentalResearchContext) -> None:
    """Identical-context invariant: fail the RUN, never compare across
    different contexts (§11 reproducibility)."""
    if record.context_version != ctx.context_version or record.context_hash != ctx.context_hash:
        raise EvaluationInvariantError(
            f"evaluation record for {record.provider}/{record.model} references "
            f"{record.context_version}/{record.context_hash} but the run context is "
            f"{ctx.context_version}/{ctx.context_hash}"
        )


async def _emit_model_event(
    emitter, ctx: FundamentalResearchContext, target: ModelTarget, *, status: str, error=None
) -> None:
    # Duck-typed: any emitter exposing async emit() works; test emitters
    # without one simply skip audit emission.
    emit = getattr(emitter, "emit", None)
    if emit is None:
        return
    payload: dict[str, Any] = {
        "symbol": ctx.symbol,
        "provider": target.provider,
        "model": target.model,
        "status": status,
    }
    if error:
        payload["error"] = error[:300]
    await emit(
        agent_id="model_evaluation_runner",
        event_type="evaluation_model_finished",
        payload=payload,
    )


def _evidence_coverage(claim_checks: list[dict]) -> float | None:
    """Fraction of evidence-existence checks that are SUPPORTED. None when
    the thesis cited no evidence ids (nothing to cover)."""
    evidence_checks = [
        c for c in claim_checks if str(c.get("statement", "")).startswith("evidence:")
    ]
    if not evidence_checks:
        return None
    supported = sum(
        1 for c in evidence_checks if c.get("status") == ClaimCheckStatus.SUPPORTED.value
    )
    return supported / len(evidence_checks)


__all__ = [
    "AGENT_PROMPT_VERSION",
    "CONTEXT_VERSION",
    "EVALUATION_AGENT_ID",
    "EVALUATION_AGENT_VERSION",
    "ContextBuilder",
    "EvaluationInvariantError",
    "EvaluationRecord",
    "EvaluationReport",
    "EvaluationRunResult",
    "GatewayFactory",
    "ModelTarget",
    "evaluate_model",
    "run_evaluation",
]
