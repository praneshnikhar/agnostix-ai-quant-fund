"""OpenRouter adapter (M2.3).

First real external LLM provider, integrated through the EXISTING gateway
seam — no second abstraction. Normalizes OpenRouter's chat-completions
response into the internal ModelResponse contract; provider-specific
objects never cross into agents/domain code.

Configuration (server-side only; never logged/persisted/committed):
- API_OPENROUTER_API_KEY   : credential (required)
- API_OPENROUTER_MODEL     : default model id (arbitrary OpenRouter id;
  per-target ids can override via the adapter constructor for evaluation)

Retry policy: bounded exponential backoff for transient failures only
(network errors, HTTP 429, 5xx). Auth/validation/model errors fail
immediately. The final failure propagates as a structured gateway error.
"""

from __future__ import annotations

import asyncio
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

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Statuses that are NEVER retried: the request itself is wrong or the
# credential is bad — retrying cannot help and would only burn quota.
_NON_RETRYABLE_STATUSES = {400, 401, 402, 403, 404, 422}


class OpenRouterAdapter(ProviderAdapter):
    name = ProviderName.OPENROUTER.value

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        model: str | None = None,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        # Explicit per-adapter model wins (evaluation targets); otherwise a
        # configured default is required at call time. No hardcoded model.
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self._transport = transport  # injection seam for mocked tests

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _model_for(self) -> str:
        if self._model:
            return self._model
        raise ProviderNotConfiguredError(
            "no OpenRouter model configured: set API_OPENROUTER_MODEL "
            "or construct the adapter with an explicit model id"
        )

    def _payload_for(self, request: ModelRequest) -> dict:
        payload: dict = {
            "model": self._model_for(),
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.response_schema is not None:
            # Structured-output instruction: JSON mode + explicit schema hint
            # so the model is told exactly which contract to satisfy.
            payload["response_format"] = {"type": "json_object"}
            schema_json = json.dumps(request.response_schema, sort_keys=True)
            payload["messages"] = [
                *payload["messages"],
                {
                    "role": "system",
                    "content": (
                        "Respond with ONE JSON object validating this "
                        "JSON Schema:" + chr(10) + schema_json
                    ),
                },
            ]
        return payload

    @staticmethod
    def _headers(api_key: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "X-Title": "Agnostix AI Quant Fund"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.is_configured:
            raise ProviderNotConfiguredError("OPENROUTER_API_KEY is not set")
        requested_model = self._model_for()
        payload = self._payload_for(request)

        started = time.monotonic()
        attempt = 0
        while True:
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds, transport=self._transport
                ) as client:
                    resp = await client.post(
                        API_URL,
                        headers=self._headers(self.api_key),
                        json=payload,
                    )
            except httpx.TransportError:
                # Transient network failure: bounded retry with backoff.
                if attempt >= self._max_retries:
                    raise
            else:
                status = resp.status_code
                if status in _NON_RETRYABLE_STATUSES:
                    # Deliberately terse: never echo request bodies/keys.
                    raise RuntimeError(f"OpenRouter rejected the request (HTTP {status})")
                if status == 429 or 500 <= status < 600:
                    if attempt < self._max_retries:
                        await self._backoff_sleep(attempt)
                        attempt += 1
                        continue
                    resp.raise_for_status()  # final attempt failed
                break
            await self._backoff_sleep(attempt)
            attempt += 1

        latency_ms = int((time.monotonic() - started) * 1000)
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = str(message.get("content", "") or "")
        usage_raw = data.get("usage") or {}
        cost = usage_raw.get("cost", usage_raw.get("total_cost"))
        return ModelResponse(
            request_id=uuid.uuid4(),
            provider=ProviderName.OPENROUTER,
            # Model id AS SERVED by the provider (may differ from requested).
            model=str(data.get("model") or requested_model),
            requested_model=requested_model,
            content=content,
            structured=_parse_json_content(content),
            finish_reason=_str_or_none(choice.get("finish_reason")),
            usage=Usage(
                prompt_tokens=_int_or_none(usage_raw.get("prompt_tokens")),
                completion_tokens=_int_or_none(usage_raw.get("completion_tokens")),
                total_tokens=_int_or_none(usage_raw.get("total_tokens")),
                estimated_cost_usd=float(cost) if isinstance(cost, (int, float)) else None,
            ),
            latency_ms=latency_ms,
        )

    async def _backoff_sleep(self, attempt: int) -> None:
        delay = self._retry_backoff_seconds * (2**attempt)
        if delay > 0:
            await asyncio.sleep(delay)


def _int_or_none(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str_or_none(value) -> str | None:
    return str(value) if value is not None else None


def _parse_json_content(content: str) -> dict | None:
    """Best-effort parse of a JSON-mode response body. Malformed output
    stays malformed downstream (agent raises a structured failure) — it is
    NEVER silently coerced into valid research."""
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


__all__ = ["OpenRouterAdapter"]
