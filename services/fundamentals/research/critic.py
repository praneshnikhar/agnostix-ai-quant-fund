"""FundamentalResearchCritic (M2, .clinerules §19/§20).

Functionally and promptually separate from the proposing agent. Runs
deterministic grounding checks FIRST — those are authoritative. An
optional LLM review adds qualitative findings but can never overturn a
deterministic failure. The critic never rewrites the thesis.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from agents.contracts import AgentRole, AgentSpec, ToolPermission
from agents.events import EventEmitter
from agents.roles import CriticAgent
from fundamentals.context import FundamentalResearchContext
from fundamentals.research.grounding import run_deterministic_checks
from fundamentals.research.schemas import (
    ClaimCheck,
    ClaimCheckStatus,
    CriticFinding,
    CriticReviewOutput,
    InvestmentThesis,
    Verdict,
)

PROMPT_VERSION = "m2-critic-v1"

CRITIC_SYSTEM_PROMPT = """You are an independent research critic. You did NOT
write the thesis under review.

Evaluate ONLY against the supplied context:
- factual grounding, evidence coverage, numerical consistency
- unsupported claims, missing risks/counterarguments
- valuation reasoning, confidence calibration, data-quality awareness

Do not rewrite the thesis. Report structured findings only.
Respond with JSON: {"verdict": "PASS|REVISE|REJECT", "findings":
[{"category","severity","detail"}], "notes": str}."""


class CriticInput(BaseModel):
    context: FundamentalResearchContext
    thesis: InvestmentThesis


class CriticResult(BaseModel):
    review: CriticReviewOutput
    critic_agent_id: str
    prompt_version: str
    llm_provider: str | None = None
    llm_model: str | None = None


class FundamentalResearchCritic(CriticAgent):
    def __init__(self, emitter: EventEmitter, gateway=None) -> None:
        spec = AgentSpec(
            agent_id="fundamental_research_critic",
            version="v1",
            role=AgentRole.CRITIC,
            description="Independent verification of fundamental research output.",
            input_schema_name="CriticInput",
            output_schema_name="CriticReviewOutput",
            model_class="standard",
            prompt_version=PROMPT_VERSION,
        )
        super().__init__(spec, emitter)
        self._gateway = gateway  # optional; deterministic checks always run

    async def run(self, input_data: BaseModel) -> CriticResult:
        if not isinstance(input_data, CriticInput):
            raise TypeError("FundamentalResearchCritic requires CriticInput")
        ctx, thesis = input_data.context, input_data.thesis

        await self.emitter.emit(
            agent_id=self.qualified_id,
            event_type="research_critic_started",
            payload={"symbol": ctx.symbol},
        )

        det = run_deterministic_checks(thesis, ctx)
        findings = [CriticFinding.model_validate(f) for f in det["findings"]]
        claim_checks = [ClaimCheck.model_validate(c) for c in det["claim_checks"]]

        verdict = Verdict.PASS
        if not det["passed"]:
            verdict = Verdict.REJECT if det["contradicted_count"] else Verdict.REVISE

        llm_provider = llm_model = None
        if self._gateway is not None:
            try:
                response = await self._gateway.run(
                    task="fundamental_critic",
                    model_class="standard",
                    messages=[
                        {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "context_summary": ctx.unavailable,
                                    "thesis": thesis.model_dump(mode="json"),
                                },
                                sort_keys=True,
                            ),
                        },
                    ],
                    caller_agent_id=self.qualified_id,
                    prompt_version=PROMPT_VERSION,
                    temperature=0.0,
                )
                payload = _extract(response)
                if payload and payload.get("verdict") in {v.value for v in Verdict}:
                    llm_verdict = Verdict(payload["verdict"])
                    # Deterministic failures are authoritative; LLM can only
                    # escalate PASS→REVISE/REJECT, never downgrade a failure.
                    if det["passed"]:
                        verdict = llm_verdict
                    for f in payload.get("findings", []):
                        try:
                            findings.append(CriticFinding.model_validate(f))
                        except ValidationError:
                            continue
                    provider = getattr(response, "provider", None) or (response.get("provider") if isinstance(response, dict) else None)
                    model = getattr(response, "model", None) or (response.get("model") if isinstance(response, dict) else None)
                    llm_provider = str(getattr(provider, "value", provider)) if provider else None
                    llm_model = str(model) if model else None
            except Exception:
                # LLM critic unavailability must not block deterministic verdict.
                pass

        review = CriticReviewOutput(
            verdict=verdict,
            findings=findings,
            claim_checks=claim_checks,
            deterministic_checks_passed=det["passed"],
        )
        await self.emitter.emit(
            agent_id=self.qualified_id,
            event_type="research_critic_completed",
            payload={"symbol": ctx.symbol, "verdict": verdict.value},
        )
        return CriticResult(
            review=review,
            critic_agent_id=self.qualified_id,
            prompt_version=PROMPT_VERSION,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )


def _extract(response: Any) -> dict | None:
    raw = getattr(response, "content", None) or (response.get("content") if isinstance(response, dict) else None)
    structured = getattr(response, "structured", None) or (response.get("structured") if isinstance(response, dict) else None)
    if isinstance(structured, dict):
        return structured
    if raw:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


__all__ = ["CriticInput", "CriticResult", "FundamentalResearchCritic"]