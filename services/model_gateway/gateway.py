"""ModelGateway — the ONLY path from agents to LLM providers.

Usage:

    gateway = ModelGateway.from_settings()
    response = await gateway.run(
        task="fundamental_analysis",
        model_class=ModelClass.REASONING,
        messages=[Message(role="user", content="...")],
        caller_agent_id="fundamental_agent_v1",
    )

The gateway:
- routes by model class + provider availability
- records telemetry (provider, model, latency, tokens, cost, success)
- never logs secrets
"""

from __future__ import annotations

import json
import uuid

from model_gateway.providers.anthropic import AnthropicAdapter
from model_gateway.providers.base import (
    ProviderAdapter,
    ProviderNotConfiguredError,
)
from model_gateway.providers.ollama import OllamaAdapter
from model_gateway.providers.openai import OpenAIAdapter
from model_gateway.schemas import (
    CallTelemetry,
    Message,
    ModelClass,
    ModelRequest,
    ModelResponse,
    TelemetrySink,
)


class NoProviderConfiguredError(RuntimeError):
    """Raised when no provider credentials are available for a call."""


class ModelGateway:
    """Provider-agnostic entry point for all model access."""

    def __init__(
        self,
        adapters: list[ProviderAdapter] | None = None,
        telemetry: TelemetrySink | None = None,
        routing_preference: list[str] | None = None,
    ) -> None:
        self._adapters: dict[str, ProviderAdapter] = {
            a.name: a for a in (adapters or [])
        }
        self.telemetry = telemetry or TelemetrySink()
        # Preference order; first configured provider wins unless overridden.
        self._routing_preference = routing_preference or [
            "anthropic",
            "openai",
            "ollama",
        ]

    @classmethod
    def from_settings(cls) -> ModelGateway:
        """Build a gateway from application settings."""
        from app.core.config import get_settings  # local import avoids cycle

        s = get_settings()
        adapters: list[ProviderAdapter] = [
            AnthropicAdapter(api_key=s.anthropic_api_key),
            OpenAIAdapter(api_key=s.openai_api_key),
            OllamaAdapter(base_url=s.ollama_base_url),
        ]
        return cls(adapters=adapters)

    def _select_adapter(self, model_class: ModelClass) -> ProviderAdapter:
        """Pick the first configured adapter per routing preference.

        Embeddings prefer a local provider when available (cost).
        """
        order = list(self._routing_preference)
        if model_class == ModelClass.EMBEDDING:
            # Prefer local embeddings when configured.
            order = ["ollama", *[p for p in order if p != "ollama"]]

        for name in order:
            adapter = self._adapters.get(name)
            if adapter is not None and adapter.is_configured:
                return adapter
        raise NoProviderConfiguredError(
            f"No provider configured for model_class={model_class}. "
            "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OLLAMA_BASE_URL."
        )

    async def run(
        self,
        task: str,
        model_class: ModelClass,
        messages: list[Message],
        caller_agent_id: str | None = None,
        prompt_version: str = "v0",
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_schema: dict | None = None,
    ) -> ModelResponse:
        """Execute one gateway call with full telemetry recording."""
        request = ModelRequest(
            task=task,
            model_class=model_class,
            messages=messages,
            response_schema=response_schema,
            prompt_version=prompt_version,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        adapter = self._select_adapter(model_class)

        try:
            response = await adapter.generate(request)
        except ProviderNotConfiguredError as exc:
            self._record_failure(request, adapter, str(exc), caller_agent_id)
            raise
        except Exception as exc:  # noqa: BLE001 - record then re-raise
            self._record_failure(request, adapter, repr(exc), caller_agent_id)
            raise

        self.telemetry.record(
            CallTelemetry(
                request_id=response.request_id,
                task=task,
                model_class=model_class,
                provider=response.provider,
                model=response.model,
                prompt_version=prompt_version,
                latency_ms=response.latency_ms,
                success=True,
                usage=response.usage,
                caller_agent_id=caller_agent_id,
            )
        )
        return response

    def _record_failure(
        self,
        request: ModelRequest,
        adapter: ProviderAdapter,
        error: str,
        caller_agent_id: str | None,
    ) -> None:
        self.telemetry.record(
            CallTelemetry(
                request_id=request.metadata.get("request_id") or uuid.uuid4(),
                task=request.task,
                model_class=request.model_class,
                provider=adapter.name,  # type: ignore[arg-type]
                model="unavailable",
                prompt_version=request.prompt_version,
                latency_ms=0,
                success=False,
                error=error[:500],
                caller_agent_id=caller_agent_id,
            )
        )

    def structured_json(self, response: ModelResponse) -> dict | None:
        """Best-effort parse of a JSON structured output."""
        if not response.content:
            return None
        try:
            return json.loads(response.content)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            return None
