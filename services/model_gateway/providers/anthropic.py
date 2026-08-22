"""Anthropic adapter (Claude family).

Uses the REST API via httpx so the gateway has no hard SDK dependency.
Only used when ANTHROPIC_API_KEY is configured.
"""

from __future__ import annotations

import time
import uuid

import httpx

from model_gateway.providers.base import ProviderAdapter, ProviderNotConfiguredError
from model_gateway.schemas import (
    ModelClass,
    ModelRequest,
    ModelResponse,
    ProviderName,
    Usage,
)

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

# Coarse default model mapping; refined by routing policy over time.
DEFAULT_MODELS: dict[ModelClass, str] = {
    ModelClass.REASONING: "claude-sonnet-4-5",
    ModelClass.STANDARD: "claude-sonnet-4-5",
    ModelClass.CHEAP: "claude-haiku-4-5",
    ModelClass.EMBEDDING: "claude-haiku-4-5",  # Anthropic has no embeddings API
}


class AnthropicAdapter(ProviderAdapter):
    name = ProviderName.ANTHROPIC.value

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _model_for(self, model_class: ModelClass) -> str:
        return DEFAULT_MODELS.get(model_class, DEFAULT_MODELS[ModelClass.STANDARD])

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.is_configured:
            raise ProviderNotConfiguredError("ANTHROPIC_API_KEY is not set")

        system_text = chr(10).join(m.content for m in request.messages if m.role == "system")
        chat_messages = [
            {"role": m.role, "content": m.content} for m in request.messages if m.role != "system"
        ]

        payload: dict[str, object] = {
            "model": self._model_for(request.model_class),
            "max_tokens": request.max_tokens or 2048,
            "messages": chat_messages,
        }
        if system_text:
            payload["system"] = system_text
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        started = time.monotonic()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                API_URL,
                headers={
                    "x-api-key": self.api_key or "",
                    "anthropic-version": API_VERSION,
                    "content-type": "application/json",
                },
                json=payload,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            resp.raise_for_status()
            data = resp.json()

        usage_raw = data.get("usage", {})
        return ModelResponse(
            request_id=uuid.uuid4(),
            provider=ProviderName.ANTHROPIC,
            model=str(data.get("model", "unknown")),
            content="".join(block.get("text", "") for block in data.get("content", [])),
            usage=Usage(
                prompt_tokens=usage_raw.get("input_tokens"),
                completion_tokens=usage_raw.get("output_tokens"),
                total_tokens=(
                    (usage_raw.get("input_tokens") or 0) + (usage_raw.get("output_tokens") or 0)
                )
                or None,
            ),
            latency_ms=latency_ms,
        )
