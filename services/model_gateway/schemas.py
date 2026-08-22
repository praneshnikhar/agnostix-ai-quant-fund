"""Model gateway schemas — typed request/response/telemetry contracts.

Every agent LLM call flows through these structures. No agent may import
a provider SDK directly.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelClass(StrEnum):
    """Coarse workload classes used for routing decisions."""

    REASONING = "reasoning"      # strong reasoning models (committee, analysis)
    STANDARD = "standard"        # general-purpose tasks
    CHEAP = "cheap"              # extraction, classification, high-frequency
    EMBEDDING = "embedding"      # vector embeddings


class ProviderName(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ModelRequest(BaseModel):
    """A single gateway call. `task` enables routing + cost attribution."""

    task: str                       # e.g. fundamental_analysis, news_extraction
    model_class: ModelClass
    messages: list[Message]
    response_schema: dict[str, Any] | None = None   # JSON-schema hint for structured output
    prompt_version: str = "v0"
    max_tokens: int | None = None
    temperature: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None


class ModelResponse(BaseModel):
    request_id: uuid.UUID
    provider: ProviderName
    model: str
    content: str
    structured: dict[str, Any] | None = None
    usage: Usage = Field(default_factory=Usage)
    latency_ms: int
    success: bool = True
    error: str | None = None


class CallTelemetry(BaseModel):
    """Recorded for every gateway call — feeds fund-economics analytics."""

    request_id: uuid.UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    task: str
    model_class: ModelClass
    provider: ProviderName
    model: str
    prompt_version: str
    latency_ms: int
    success: bool
    error: str | None = None
    usage: Usage = Field(default_factory=Usage)
    caller_agent_id: str | None = None


class TelemetrySink:
    """Pluggable telemetry sink interface.

    M0 default keeps an in-memory ring buffer; a DB-backed sink lands with
    the observability milestone. Never log secrets here.
    """

    def __init__(self, max_records: int = 10_000) -> None:
        self._records: list[CallTelemetry] = []
        self._max_records = max_records

    def record(self, telemetry: CallTelemetry) -> None:
        self._records.append(telemetry)
        if len(self._records) > self._max_records:
            del self._records[: len(self._records) - self._max_records]

    def snapshot(self) -> list[CallTelemetry]:
        return list(self._records)

    def total_estimated_cost_usd(self) -> float:
        return sum(t.usage.estimated_cost_usd or 0.0 for t in self._records)


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
