"""Ollama / local-model adapter.

Used when OLLAMA_BASE_URL is configured. Enables cheap/local workloads
(extraction, classification, embeddings) without external API cost.
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

DEFAULT_MODELS: dict[ModelClass, str] = {
    ModelClass.REASONING: "qwen2.5:14b",
    ModelClass.STANDARD: "llama3.1:8b",
    ModelClass.CHEAP: "llama3.1:8b",
    ModelClass.EMBEDDING: "bge-m3",
}


class OllamaAdapter(ProviderAdapter):
    name = ProviderName.OLLAMA.value

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _model_for(self, model_class: ModelClass) -> str:
        return DEFAULT_MODELS.get(model_class, DEFAULT_MODELS[ModelClass.STANDARD])

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.is_configured:
            raise ProviderNotConfiguredError("OLLAMA_BASE_URL is not set")

        payload: dict[str, object] = {
            "model": self._model_for(request.model_class),
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
        }
        if request.temperature is not None:
            payload["options"] = {"temperature": request.temperature}

        base = self.base_url or ""
        url = f"{base.rstrip('/')}/api/chat"
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json=payload)
            latency_ms = int((time.monotonic() - started) * 1000)
            resp.raise_for_status()
            data = resp.json()

        return ModelResponse(
            request_id=uuid.uuid4(),
            provider=ProviderName.OLLAMA,
            model=str(data.get("model", "unknown")),
            content=str(data.get("message", {}).get("content", "")),
            usage=Usage(
                prompt_tokens=data.get("prompt_eval_count"),
                completion_tokens=data.get("eval_count"),
                total_tokens=((data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0))
                or None,
            ),
            latency_ms=latency_ms,
        )
