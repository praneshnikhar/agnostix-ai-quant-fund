"""Custom / self-hosted model adapter.

Generic first-class provider for ANY HTTP inference endpoint that is not
covered by a dedicated adapter — e.g. vLLM, TGI, an OpenAI-compatible
self-hosted server, or a future internally fine-tuned Agnostix model.
Nothing about vLLM/TGI/etc. is hardcoded: the endpoint is fully
configurable and the OpenAI-compatible chat-completions shape is treated
as one explicitly supported wire format.

Configuration follows the existing project conventions (env prefix `API_`):
- API_CUSTOM_MODEL_BASE_URL : endpoint base (e.g. https://llm.internal/v1)
- API_CUSTOM_MODEL_API_KEY  : optional bearer credential
- API_CUSTOM_MODEL_ID       : model identifier served by the endpoint
- API_CUSTOM_MODEL_TIMEOUT_SECONDS / API_CUSTOM_MODEL_HEADERS (JSON)

Credentials are optional (private endpoints may be unauthenticated) and are
never logged or persisted. All wire-format details stay inside this adapter.
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


class CustomModelAdapter(ProviderAdapter):
    """Generic OpenAI-compatible self-hosted/custom inference adapter."""

    name = "custom"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        model: str | None = None,
        timeout_seconds: float = 120.0,
        extra_headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._extra_headers = dict(extra_headers or {})
        self._transport = transport  # injection seam for mocked tests

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _model_for(self) -> str:
        if self._model:
            return self._model
        raise ProviderNotConfiguredError(
            "no custom model configured: set API_CUSTOM_MODEL_ID "
            "or construct the adapter with an explicit model id"
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.is_configured:
            raise ProviderNotConfiguredError("CUSTOM_MODEL_BASE_URL is not set")
        requested_model = self._model_for()

        messages: list[dict[str, object]] = [
            {"role": m.role, "content": m.content} for m in request.messages
        ]
        payload: dict[str, object] = {
            "model": requested_model,
            "messages": messages,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.response_schema is not None:
            # Structured-output instruction for OpenAI-compatible servers.
            payload["response_format"] = {"type": "json_object"}
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

        headers = {"Content-Type": "application/json", **self._extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        base = (self.base_url or "").rstrip("/")
        url = f"{base}/chat/completions"
        started = time.monotonic()
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds, transport=self._transport
        ) as client:
            resp = await client.post(url, headers=headers, json=payload)
            latency_ms = int((time.monotonic() - started) * 1000)
            resp.raise_for_status()
            data = resp.json()

        choice = (data.get("choices") or [{}])[0]
        usage_raw = data.get("usage") or {}
        return ModelResponse(
            request_id=uuid.uuid4(),
            provider=ProviderName.CUSTOM,
            model=str(data.get("model") or requested_model),
            requested_model=requested_model,
            content=str((choice.get("message") or {}).get("content", "") or ""),
            finish_reason=_str_or_none(choice.get("finish_reason")),
            usage=Usage(
                prompt_tokens=_int_or_none(usage_raw.get("prompt_tokens")),
                completion_tokens=_int_or_none(usage_raw.get("completion_tokens")),
                total_tokens=_int_or_none(usage_raw.get("total_tokens")),
                estimated_cost_usd=None,  # self-hosted: no cost metadata exists
            ),
            latency_ms=latency_ms,
        )


def _int_or_none(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str_or_none(value) -> str | None:
    return str(value) if value is not None else None


__all__ = ["CustomModelAdapter"]
