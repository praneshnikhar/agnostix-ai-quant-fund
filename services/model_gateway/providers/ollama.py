"""Ollama / local-model adapter.

First-class local provider: enables offline inference once a model is
downloaded, with zero external API cost. All Ollama-specific request/
response shapes stay inside this adapter — agents only ever see the
normalized ModelResponse contract.

Configuration follows the existing project conventions (env prefix `API_`):
- API_OLLAMA_BASE_URL : server base URL (fully configurable; nothing is
  hardcoded to localhost or any host)
- API_OLLAMA_MODEL    : model id (arbitrary; e.g. qwen/deepseek/llama/
  any custom local tag). NO default model is hardcoded — an explicit id
  is required at call time.

Structured output: when the caller supplies a response schema, the adapter
requests JSON mode and appends the schema as an instruction message.
"""

from __future__ import annotations

import json
import time
import uuid

import httpx

from model_gateway.providers.base import ProviderAdapter, ProviderNotConfiguredError
from model_gateway.schemas import (
    ModelRequest,
    ModelResponse,
    ProviderName,
    Usage,
)


class OllamaAdapter(ProviderAdapter):
    name = ProviderName.OLLAMA.value

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        model: str | None = None,
        timeout_seconds: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        # Local inference needs no credential; base URL + explicit model id
        # are what matter. No hardcoded host, GPU, or model.
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport  # injection seam for mocked tests

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _model_for(self) -> str:
        if self._model:
            return self._model
        raise ProviderNotConfiguredError(
            "no Ollama model configured: set API_OLLAMA_MODEL "
            "or construct the adapter with an explicit model id"
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.is_configured:
            raise ProviderNotConfiguredError("OLLAMA_BASE_URL is not set")
        requested_model = self._model_for()

        messages: list[dict[str, object]] = [
            {"role": m.role, "content": m.content} for m in request.messages
        ]
        payload: dict[str, object] = {
            "model": requested_model,
            "messages": messages,
            "stream": False,
        }
        options: dict[str, object] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if options:
            payload["options"] = options
        if request.response_schema is not None:
            # Constrained structured output: pass the JSON Schema to Ollama's
            # `format` so the model is forced to emit conformant JSON, plus a
            # plain-language schema hint for value quality.
            payload["format"] = request.response_schema
            schema_json = json.dumps(request.response_schema, sort_keys=True)
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Respond with ONE JSON object validating this "
                        "JSON Schema:" + chr(10) + schema_json
                    ),
                }
            )
            payload["messages"] = messages

        base = self.base_url or ""
        url = f"{base.rstrip('/')}/api/chat"
        started = time.monotonic()
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds, transport=self._transport
        ) as client:
            resp = await client.post(url, json=payload)
            latency_ms = int((time.monotonic() - started) * 1000)
            resp.raise_for_status()
            data = resp.json()

        prompt_tokens = _int_or_none(data.get("prompt_eval_count"))
        completion_tokens = _int_or_none(data.get("eval_count"))
        total = (
            (prompt_tokens + completion_tokens)
            if prompt_tokens is not None and completion_tokens is not None
            else None
        )
        return ModelResponse(
            request_id=uuid.uuid4(),
            provider=ProviderName.OLLAMA,
            # Model id AS SERVED by the local runtime.
            model=str(data.get("model") or requested_model),
            requested_model=requested_model,
            content=str((data.get("message") or {}).get("content", "") or ""),
            finish_reason=_str_or_none(data.get("done_reason")),
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
                estimated_cost_usd=None,  # local inference: no cost metadata exists
            ),
            latency_ms=latency_ms,
        )


def _int_or_none(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str_or_none(value) -> str | None:
    return str(value) if value is not None else None


__all__ = ["OllamaAdapter"]
