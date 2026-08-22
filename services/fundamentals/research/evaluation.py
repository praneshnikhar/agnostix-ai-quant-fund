"""Model evaluation harness (M2, .clinerules §21/§22).

Runs the identical research task against multiple models/providers through
the Model Gateway and records per-run telemetry: provider, model, prompt
version, latency, tokens, estimated cost, success, schema validity, critic
result. Normal CI uses mocked gateways only — never live LLM calls.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from fundamentals.context import FundamentalResearchContext
from fundamentals.research.agent import PROMPT_VERSION as AGENT_PROMPT_VERSION
from fundamentals.research.agent import FundamentalResearchAgent
from fundamentals.research.critic import CriticInput, FundamentalResearchCritic
from fundamentals.research.schemas import Verdict


class EvaluationRecord(BaseModel):
    provider: str
    model: str
    task: str = "fundamental_analysis"
    prompt_version: str = AGENT_PROMPT_VERSION
    context_hash: str
    symbol: str
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    success: bool = False
    schema_valid: bool = False
    error: str | None = None
    fundamental_view: str | None = None
    confidence: float | None = None
    critic_verdict: Verdict | None = None
    unsupported_claims: int = 0
    contradicted_claims: int = 0


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
                    "success": 0,
                    "schema_valid": 0,
                    "critic_pass": 0,
                    "unsupported_claims": 0,
                    "contradicted_claims": 0,
                    "total_latency_ms": 0,
                    "total_cost_usd": 0.0,
                },
            )
            s["runs"] += 1
            s["success"] += int(r.success)
            s["schema_valid"] += int(r.schema_valid)
            s["critic_pass"] += int(r.critic_verdict == Verdict.PASS)
            s["unsupported_claims"] += r.unsupported_claims
            s["contradicted_claims"] += r.contradicted_claims
            s["total_latency_ms"] += r.latency_ms
            s["total_cost_usd"] += r.estimated_cost_usd or 0.0
        return by_model


async def evaluate_model(
    gateway,
    emitter,
    ctx: FundamentalResearchContext,
    *,
    provider_label: str,
    model_label: str,
) -> EvaluationRecord:
    """Run one agent+critic cycle against a (possibly mocked) gateway."""
    record = EvaluationRecord(
        provider=provider_label, model=model_label, context_hash=ctx.context_hash, symbol=ctx.symbol
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
        record.unsupported_claims = _count_unsupported(run_result.thesis.model_dump(mode="json"), ctx)
        critic = FundamentalResearchCritic(emitter)
        critic_out = await critic.run(CriticInput(context=ctx, thesis=run_result.thesis))
        record.critic_verdict = critic_out.review.verdict
        record.contradicted_claims = sum(
            1 for c in critic_out.review.claim_checks if c.status.value == "CONTRADICTED"
        )
    except Exception as exc:
        record.success = False
        record.error = repr(exc)[:500]
        record.latency_ms = int((time.perf_counter() - start) * 1000)
    return record


def _count_unsupported(thesis_payload: dict, ctx: FundamentalResearchContext) -> int:
    from fundamentals.research.grounding import run_deterministic_checks
    from fundamentals.research.schemas import InvestmentThesis

    try:
        thesis = InvestmentThesis.model_validate(thesis_payload)
    except Exception:
        return 0
    det = run_deterministic_checks(thesis, ctx)
    return int(det["unsupported_count"]) + int(det["contradicted_count"])


__all__ = ["EvaluationRecord", "EvaluationReport", "evaluate_model"]