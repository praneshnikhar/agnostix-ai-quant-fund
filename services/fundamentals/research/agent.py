"""FundamentalResearchAgent (M2, .clinerules §13/§17).

Uses the existing Agent Runtime (BaseAgent/roles) and Model Gateway.
Receives a FundamentalResearchContext; produces a strictly structured
InvestmentThesis via the gateway's structured output. Hallucination rules
are enforced promptually AND structurally (schema validation + grounding
checks downstream in the critic).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from agents.contracts import AgentRole, AgentSpec, ToolPermission
from agents.events import EventEmitter
from agents.roles import ResearchAgent
from fundamentals.context import FundamentalResearchContext, render_context_for_model
from fundamentals.research.schemas import InvestmentThesis

PROMPT_VERSION = "m2-fundamental-v1"

SYSTEM_PROMPT = """You are a rigorous fundamental equity research analyst.

HARD RULES (violations invalidate your output):
- Use ONLY the supplied context. Do not invent facts, financial values,
  sources, URLs, or documents.
- Never claim access to documents or data not present in the context.
- Distinguish FACTS (numbers/events from context) from INTERPRETATION
  (your reasoning) from CONCLUSION (your view).
- If required information is unavailable, say so structurally: use
  INSUFFICIENT_DATA as fundamental_view and list the gap in limitations.
- Confidence expresses confidence in the QUALITY/STRENGTH of your research
  conclusion — it is NOT a probability of future stock return.
- Every major conclusion must reference evidence ids that exist in the
  context.
- Do not perform arithmetic beyond simple reading of provided derived
  metrics; all supplied numbers are pre-computed and authoritative.

Respond with a single JSON object matching the requested schema."""


class AgentRunResult(BaseModel):
    """Agent output + full reproducibility metadata (§23)."""

    thesis: InvestmentThesis
    provider: str
    model: str
    prompt_version: str
    agent_id: str
    agent_version: str
    context_version: str
    context_hash: str
    latency_ms: int


def _response_schema() -> dict:
    return InvestmentThesis.model_json_schema()


class FundamentalResearchAgent(ResearchAgent):
    """READ_* + WRITE_RESEARCH only. NO execution permissions."""

    def __init__(self, gateway, emitter: EventEmitter) -> None:
        spec = AgentSpec(
            agent_id="fundamental_research_agent",
            version="v1",
            role=AgentRole.RESEARCH,
            description="Evidence-backed fundamental research over deterministic data.",
            input_schema_name="FundamentalResearchContext",
            output_schema_name="InvestmentThesis",
            model_class="reasoning",
            prompt_version=PROMPT_VERSION,
        )
        super().__init__(spec, emitter)
        # Explicit least-privilege grant set (§28): no PLACE_ORDER /
        # MODIFY_PORTFOLIO / BYPASS_RISK exists anywhere in this codebase.
        self.spec.tool_permissions = frozenset(
            {
                ToolPermission.READ_MARKET_DATA,
                ToolPermission.READ_NEWS,
                ToolPermission.READ_SNAPSHOT,
                ToolPermission.VERIFY_EVIDENCE,
            }
        )
        self._gateway = gateway

    async def run(self, input_data: BaseModel) -> AgentRunResult:
        if not isinstance(input_data, FundamentalResearchContext):
            raise TypeError("FundamentalResearchAgent requires FundamentalResearchContext")
        ctx = input_data
        await self.emitter.emit(
            agent_id=self.qualified_id,
            event_type="research_agent_started",
            payload={"symbol": ctx.symbol, "context_hash": ctx.context_hash},
        )
        rendered = render_context_for_model(ctx)
        try:
            response = await self._gateway.run(
                task="fundamental_analysis",
                model_class=self._gateway.ModelClass.REASONING
                if hasattr(self._gateway, "ModelClass")
                else "reasoning",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": rendered},
                ],
                caller_agent_id=self.qualified_id,
                prompt_version=PROMPT_VERSION,
                response_schema=_response_schema(),
                temperature=0.2,
            )
        except Exception as exc:
            await self.emitter.emit(
                agent_id=self.qualified_id,
                event_type="research_agent_failed",
                payload={"symbol": ctx.symbol, "error": repr(exc)[:500]},
            )
            raise

        raw = response.get("content") if isinstance(response, dict) else getattr(response, "content", None)
        provider = response.get("provider") if isinstance(response, dict) else getattr(response, "provider", "unknown")
        model = response.get("model") if isinstance(response, dict) else getattr(response, "model", "unknown")
        latency = response.get("latency_ms") if isinstance(response, dict) else getattr(response, "latency_ms", 0)
        structured = response.get("structured") if isinstance(response, dict) else getattr(response, "structured", None)
        payload = structured if isinstance(structured, dict) else _parse_json(raw)

        if payload is None:
            await self.emitter.emit(
                agent_id=self.qualified_id,
                event_type="research_agent_failed",
                payload={"symbol": ctx.symbol, "error": "unparseable model output"},
            )
            raise ValueError("model returned unparseable output")

        payload.setdefault("symbol", ctx.symbol)
        payload.setdefault("research_timestamp", datetime.now(UTC).isoformat())
        try:
            thesis = InvestmentThesis.model_validate(payload)
        except ValidationError as exc:
            await self.emitter.emit(
                agent_id=self.qualified_id,
                event_type="research_agent_failed",
                payload={"symbol": ctx.symbol, "error": f"schema violation: {exc.errors()[:3]}"},
            )
            raise

        result = AgentRunResult(
            thesis=thesis,
            provider=str(getattr(provider, "value", provider)),
            model=str(model),
            prompt_version=PROMPT_VERSION,
            agent_id=self.spec.agent_id,
            agent_version=self.spec.version,
            context_version=ctx.context_version,
            context_hash=ctx.context_hash,
            latency_ms=int(latency or 0),
        )
        await self.emitter.emit(
            agent_id=self.qualified_id,
            event_type="research_agent_completed",
            payload={
                "symbol": ctx.symbol,
                "view": thesis.fundamental_view.value,
                "confidence": thesis.confidence,
                "provider": result.provider,
                "model": result.model,
            },
        )
        return result


def _parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None