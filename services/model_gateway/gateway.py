"""ModelGateway — the ONLY path from agents to LLM providers.

Usage:

    gateway = ModelGateway.from_settings()
    response = await gateway.run(
        task="fundamental_analysis",
        model_class=ModelClass.REASONING,
        messages=[Message(role="user", content="...")],
        caller_agent_id="fundamental_agent_v1",
    )

Provider-agnostic by design (.clinerules §5): agents depend ONLY on this
module and its normalized contracts — never on a provider SDK/adapter.
Providers are resolved through a single REGISTRY (no second registry may be
created); every category is first-class:

    cloud      : anthropic / openai / openrouter
    local      : ollama (works fully offline once models are downloaded)
    custom     : any self-hosted / OpenAI-compatible HTTP endpoint

Pinned single-provider gateways come from the same registry:

    get_model_gateway(provider="openrouter", model="<id>")
    get_model_gateway(provider="ollama",     model="<id>")
    get_model_gateway(provider="custom",     model="<id>")

Unknown providers fail cleanly with UnknownProviderError.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from model_gateway.providers.anthropic import AnthropicAdapter
from model_gateway.providers.base import (
    ProviderAdapter,
    ProviderNotConfiguredError,
)
from model_gateway.providers.custom import CustomModelAdapter
from model_gateway.providers.ollama import OllamaAdapter
from model_gateway.providers.openai import OpenAIAdapter
from model_gateway.providers.openrouter import OpenRouterAdapter
from model_gateway.schemas import (
    CallTelemetry,
    Message,
    ModelClass,
    ModelRequest,
    ModelResponse,
    TelemetrySink,
)

if TYPE_CHECKING:
    from app.core.config import Settings


class NoProviderConfiguredError(RuntimeError):
    """Raised when no provider credentials are available for a call."""


class UnknownProviderError(RuntimeError):
    """Raised when an unknown provider name is requested from the registry."""


# ---------------------------------------------------------------------------
# Provider registry — the SINGLE source of provider construction.
# Each builder receives (settings, explicit_model_override) and returns an
# adapter. Adding a provider means adding ONE entry here; nothing else in
# the codebase changes.
# ---------------------------------------------------------------------------

AdapterBuilder = Callable[["Settings", str | None], ProviderAdapter]

_ADAPTER_BUILDERS: dict[str, AdapterBuilder] = {
    "anthropic": lambda s, m: AnthropicAdapter(api_key=s.anthropic_api_key),
    "openai": lambda s, m: OpenAIAdapter(api_key=s.openai_api_key),
    "ollama": lambda s, m: OllamaAdapter(
        base_url=s.ollama_base_url,
        model=m or s.ollama_model,
        timeout_seconds=s.ollama_timeout_seconds,
    ),
    "openrouter": lambda s, m: OpenRouterAdapter(
        api_key=s.openrouter_api_key,
        model=m or s.openrouter_model,
        timeout_seconds=s.openrouter_timeout_seconds,
        max_retries=s.openrouter_max_retries,
        retry_backoff_seconds=s.openrouter_retry_backoff_seconds,
    ),
    "custom": lambda s, m: CustomModelAdapter(
        base_url=s.custom_model_base_url,
        api_key=s.custom_model_api_key,
        model=m or s.custom_model_id,
        timeout_seconds=s.custom_model_timeout_seconds,
        extra_headers=dict(s.custom_model_headers or {}),
    ),
}

# Default routing order; new providers append at the TAIL so existing
# behavior is unchanged unless earlier providers are unconfigured.
_DEFAULT_ROUTING = ["anthropic", "openai", "ollama", "openrouter", "custom"]


def known_providers() -> list[str]:
    """All provider names registered in the gateway."""
    return sorted(_ADAPTER_BUILDERS)


def _build_all_adapters(settings: Settings) -> list[ProviderAdapter]:
    return [_ADAPTER_BUILDERS[name](settings, None) for name in _DEFAULT_ROUTING]


def get_model_gateway(provider: str, *, model: str | None = None) -> ModelGateway:
    """Return a gateway pinned to ONE registered provider (+ optional model).

    The SAME internal ModelGateway contract is returned for every provider
    category (cloud/local/custom). Unknown providers raise cleanly.
    """
    from app.core.config import get_settings  # local import avoids cycle

    builder = _ADAPTER_BUILDERS.get(provider)
    if builder is None:
        raise UnknownProviderError(
            f"unknown model provider {provider!r}; known providers: {known_providers()}"
        )
    adapter = builder(get_settings(), model)
    return ModelGateway(adapters=[adapter], routing_preference=[provider])


def get_model_gateway_for_configuration(
    provider: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float | None = None,
    extra_headers: dict[str, str] | None = None,
) -> ModelGateway:
    """Resolve a stored provider configuration through the same registry.

    This is the configuration-aware seam for provider management. It does
    not create a second registry and does not change the public gateway
    contract used by agents.
    """
    from app.core.config import get_settings

    settings = get_settings().model_copy(
        update={
            "anthropic_api_key": api_key,
            "openai_api_key": api_key,
            "openrouter_api_key": api_key,
            "ollama_base_url": base_url,
            "custom_model_base_url": base_url,
            "custom_model_api_key": api_key,
            "ollama_timeout_seconds": timeout_seconds or get_settings().ollama_timeout_seconds,
            "openrouter_timeout_seconds": timeout_seconds
            or get_settings().openrouter_timeout_seconds,
            "custom_model_timeout_seconds": timeout_seconds
            or get_settings().custom_model_timeout_seconds,
            "custom_model_headers": extra_headers or {},
        }
    )
    builder = _ADAPTER_BUILDERS.get(provider)
    if builder is None:
        raise UnknownProviderError(f"unknown model provider {provider!r}")
    return ModelGateway(
        adapters=[builder(settings, model)],
        routing_preference=[provider],
    )


class ModelGateway:
    """Provider-agnostic entry point for all model access."""

    def __init__(
        self,
        adapters: list[ProviderAdapter] | None = None,
        telemetry: TelemetrySink | None = None,
        routing_preference: list[str] | None = None,
    ) -> None:
        self._adapters: dict[str, ProviderAdapter] = {a.name: a for a in (adapters or [])}
        self.telemetry = telemetry or TelemetrySink()
        # Preference order; first configured provider wins unless overridden.
        self._routing_preference = routing_preference or list(_DEFAULT_ROUTING)

    @classmethod
    def from_settings(cls) -> ModelGateway:
        """Build a gateway from application settings (ALL registered providers)."""
        from app.core.config import get_settings  # local import avoids cycle

        return cls(adapters=_build_all_adapters(get_settings()))

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
            "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, OLLAMA_BASE_URL, "
            "OPENROUTER_API_KEY, or CUSTOM_MODEL_BASE_URL."
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
            import json

            return json.loads(response.content)
        except json.JSONDecodeError:
            return None
