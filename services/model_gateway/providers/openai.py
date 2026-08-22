"""OpenAI adapter.

Uses the REST API via httpx so the gateway has no hard SDK dependency.
Only used when OPENAI_API_KEY is configured.
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

API_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_MODELS: dict[ModelClass, str] = {
    ModelClass.REASONING: "gpt-4o",
    ModelClass.STANDARD: "gpt-4o-mini",
    ModelClass.CHEAP: "gpt-4o-mini",
    ModelClass.EMBEDDING: "text-embedding-3-small",
}


class OpenAIAdapter(ProviderAdapter):
    name = ProviderName.OPENAI.value

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _model_for(self, model_class: ModelClass) -> str:
        return DEFAULT_MODELS.get(model_class, DEFAULT_MODELS[ModelClass.STANDARD])

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.is_configured:
            raise ProviderNotConfiguredError("OPENAI_API_KEY is not set")

        payload: dict[str, object] = {
            "model": self._model_for(request.model_class),
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.response_schema is not None:
            payload["response_format"] = {"type": "json_object"}

        started = time.monotonic()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        usage_raw = data.get("usage", {})
        return ModelResponse(
            request_id=uuid.uuid4(),
            provider=ProviderName.OPENAI,
            model=str(data.get("model", "unknown")),
            content=str(choice.get("message", {}).get("content", "")),
            usage=Usage(
                prompt_tokens=usage_raw.get("prompt_tokens"),
                completion_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            ),
            latency_ms=latency_ms,
        )
