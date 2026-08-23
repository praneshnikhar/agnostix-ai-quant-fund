"""Provider-agnostic model platform tests (M2.3).

Proves: single registry, clean unknown-provider failure, per-adapter
isolation, normalized-contract parity across cloud/local/custom providers,
credential non-leakage, and that the DOMAIN layer never imports provider
code. ALL HTTP is mocked via httpx.MockTransport — no live calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from model_gateway.gateway import (
    ModelGateway,
    NoProviderConfiguredError,
    UnknownProviderError,
    get_model_gateway,
    known_providers,
)
from model_gateway.providers.base import ProviderNotConfiguredError
from model_gateway.providers.custom import CustomModelAdapter
from model_gateway.providers.ollama import OllamaAdapter
from model_gateway.providers.openrouter import OpenRouterAdapter
from model_gateway.schemas import Message, ModelClass, ModelRequest, ModelResponse

KEY = "sk-test-secret-key-123"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _request(*, response_schema: dict | None = None) -> ModelRequest:
    return ModelRequest(
        task="fundamental_analysis",
        model_class=ModelClass.REASONING,
        messages=[Message(role="user", content="Analyze ACME.")],
        response_schema=response_schema,
    )


def _json(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


def _openrouter_payload(**over) -> dict:
    payload = {
        "model": "served/openrouter-id",
        "choices": [
            {"message": {"content": json.dumps({"symbol": "ACME"})}, "finish_reason": "stop"}
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": 0.0021,
        },
    }
    payload.update(over)
    return payload


# ------------------------------------------------------------------ registry


def test_registry_returns_pinned_gateway_for_every_category():
    for provider in ("openrouter", "ollama", "custom"):
        gw = get_model_gateway(provider, model="any-model-id")
        assert isinstance(gw, ModelGateway)
        assert gw._routing_preference == [provider]
        assert list(gw._adapters) == [provider]


def test_unknown_provider_fails_cleanly():
    with pytest.raises(UnknownProviderError) as ei:
        get_model_gateway("does-not-exist", model="m")
    assert "does-not-exist" in str(ei.value)
    # The error lists what IS available — actionable, not a bare KeyError.
    for known in known_providers():
        assert known in str(ei.value)


def test_registry_covers_all_four_categories():
    providers = set(known_providers())
    assert {"openrouter", "ollama", "custom", "anthropic", "openai"} <= providers


def test_provider_selection_not_hardcoded_in_agent():
    """The research agent accepts ANY gateway object — selection happens at
    the composition layer via the registry, never inside the agent."""
    import inspect

    from fundamentals.research.agent import FundamentalResearchAgent

    src = inspect.getsource(FundamentalResearchAgent)
    for forbidden in ("get_model_gateway", "OpenRouter", "Ollama", "CustomModel"):
        assert forbidden not in src


# ---------------------------------------------------------------- openrouter


def test_openrouter_request_and_response_normalization():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return _json(_openrouter_payload())

    adapter = OpenRouterAdapter(
        api_key=KEY,
        model="requested/alias",
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    resp = adapter.generate(_request(response_schema={"type": "object"}))
    import asyncio

    out = asyncio.run(resp)

    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["auth"] == f"Bearer {KEY}"
    assert captured["body"]["model"] == "requested/alias"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    # Schema hint appended as an instruction message.
    assert any("JSON Schema" in m.get("content", "") for m in captured["body"]["messages"])

    assert isinstance(out, ModelResponse)
    assert out.provider.value == "openrouter"
    assert out.model == "served/openrouter-id"  # served version
    assert out.requested_model == "requested/alias"
    assert out.finish_reason == "stop"
    assert out.usage.prompt_tokens == 100
    assert out.usage.completion_tokens == 50
    assert out.usage.total_tokens == 150
    assert out.usage.estimated_cost_usd == pytest.approx(0.0021)
    assert out.structured == {"symbol": "ACME"}


def test_openrouter_missing_api_key_is_unconfigured():
    adapter = OpenRouterAdapter(api_key=None, model="m")
    assert adapter.is_configured is False
    gateway = ModelGateway(adapters=[adapter], routing_preference=["openrouter"])
    import asyncio

    with pytest.raises(NoProviderConfiguredError):
        asyncio.run(
            gateway.run(
                task="t",
                model_class=ModelClass.STANDARD,
                messages=[Message(role="user", content="x")],
            )
        )


def test_openrouter_missing_model_fails_cleanly():
    adapter = OpenRouterAdapter(api_key=KEY, model=None)
    import asyncio

    with pytest.raises(ProviderNotConfiguredError):
        asyncio.run(adapter.generate(_request()))


def test_openrouter_retries_429_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return _json(_openrouter_payload())

    adapter = OpenRouterAdapter(
        api_key=KEY,
        model="m",
        max_retries=2,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    import asyncio

    out = asyncio.run(adapter.generate(_request()))
    assert calls["n"] == 2
    assert out.success is True


def test_openrouter_5xx_bounded_then_raises():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={"error": "down"})

    adapter = OpenRouterAdapter(
        api_key=KEY,
        model="m",
        max_retries=1,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    import asyncio

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(adapter.generate(_request()))
    assert calls["n"] == 2  # initial + 1 bounded retry; NO infinite loop


def test_openrouter_timeout_is_bounded():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectTimeout("timed out")

    adapter = OpenRouterAdapter(
        api_key=KEY,
        model="m",
        timeout_seconds=0.01,
        max_retries=1,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    import asyncio

    with pytest.raises(httpx.ConnectTimeout):
        asyncio.run(adapter.generate(_request()))
    assert calls["n"] == 2


def test_openrouter_invalid_model_fails_immediately_no_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={"error": "unknown model"})

    adapter = OpenRouterAdapter(
        api_key=KEY,
        model="bad/model",
        max_retries=3,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    import asyncio

    with pytest.raises(RuntimeError) as ei:
        asyncio.run(adapter.generate(_request()))
    assert calls["n"] == 1  # non-retryable: exactly one attempt
    assert "HTTP 404" in str(ei.value)


def test_openrouter_malformed_output_is_never_coerced():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(
            {
                "model": "served/m",
                "choices": [{"message": {"content": "this is not json"}, "finish_reason": "stop"}],
                "usage": {},
            }
        )

    adapter = OpenRouterAdapter(
        api_key=KEY,
        model="m",
        transport=httpx.MockTransport(handler),
    )
    import asyncio

    out = asyncio.run(adapter.generate(_request()))
    assert out.content == "this is not json"  # preserved verbatim
    assert out.structured is None  # malformed stays malformed downstream


def test_openrouter_missing_token_metadata_stays_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json({"model": "served/m", "choices": [{"message": {"content": "{}"}}]})

    adapter = OpenRouterAdapter(api_key=KEY, model="m", transport=httpx.MockTransport(handler))
    import asyncio

    out = asyncio.run(adapter.generate(_request()))
    assert out.usage.prompt_tokens is None
    assert out.usage.completion_tokens is None
    assert out.usage.total_tokens is None
    assert out.usage.estimated_cost_usd is None


def test_credentials_never_leak_into_errors_or_telemetry():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    sink = ModelGateway().telemetry
    adapter = OpenRouterAdapter(
        api_key=KEY, model="m", transport=httpx.MockTransport(handler)
    )
    gateway = ModelGateway(adapters=[adapter], routing_preference=["openrouter"], telemetry=sink)
    import asyncio

    with pytest.raises(Exception) as ei:
        asyncio.run(
            gateway.run(
                task="t",
                model_class=ModelClass.REASONING,
                messages=[Message(role="user", content="x")],
            )
        )
    assert KEY not in str(ei.value)
    for record in sink.snapshot():
        assert KEY not in (record.error or "")
        assert KEY not in record.model_dump(mode="json")


# -------------------------------------------------------------------- ollama


def test_ollama_requires_explicit_model_no_hardcoded_default():
    adapter = OllamaAdapter(base_url="http://any-host:11434", model=None)
    import asyncio

    with pytest.raises(ProviderNotConfiguredError):
        asyncio.run(adapter.generate(_request()))


def test_ollama_normalization_with_configured_host_and_model():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return _json(
            {
                "model": "qwen-local-tag",
                "message": {"content": json.dumps({"view": "NEUTRAL"})},
                "done_reason": "stop",
                "prompt_eval_count": 80,
                "eval_count": 40,
            }
        )

    adapter = OllamaAdapter(
        base_url="http://gpu-box.internal:11434",  # NOT hardcoded localhost
        model="my-custom-local-model",
        transport=httpx.MockTransport(handler),
    )
    import asyncio

    out = asyncio.run(adapter.generate(_request(response_schema={"type": "object"})))

    assert captured["url"].startswith("http://gpu-box.internal:11434/api/chat")
    assert captured["body"]["model"] == "my-custom-local-model"
    assert captured["body"]["format"] == "json"  # structured-output mode
    assert isinstance(out, ModelResponse)
    assert out.provider.value == "ollama"
    assert out.model == "qwen-local-tag"
    assert out.requested_model == "my-custom-local-model"
    assert out.finish_reason == "stop"
    assert out.usage.prompt_tokens == 80
    assert out.usage.completion_tokens == 40
    assert out.usage.total_tokens == 120
    assert out.usage.estimated_cost_usd is None  # local inference: no cost exists


def test_ollama_missing_base_url_is_unconfigured():
    adapter = OllamaAdapter(base_url=None, model="m")
    assert adapter.is_configured is False


# --------------------------------------------------------------------- custom


def test_custom_normalization_auth_and_extra_headers():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return _json(
            {
                "model": "finetuned-agnostix-v1",
                "choices": [
                    {"message": {"content": "{}"}, "finish_reason": "length"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

    adapter = CustomModelAdapter(
        base_url="https://llm.private.internal/v1",
        api_key=KEY,
        model="agnostix-finetune",
        extra_headers={"X-Tenant": "fund"},
        transport=httpx.MockTransport(handler),
    )
    import asyncio

    out = asyncio.run(adapter.generate(_request(response_schema={"type": "object"})))

    # httpx normalizes header names to lowercase on the wire.
    sent_headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert captured["url"] == "https://llm.private.internal/v1/chat/completions"
    assert sent_headers["authorization"] == f"Bearer {KEY}"
    assert sent_headers["x-tenant"] == "fund"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert isinstance(out, ModelResponse)
    assert out.provider.value == "custom"
    assert out.model == "finetuned-agnostix-v1"
    assert out.requested_model == "agnostix-finetune"
    assert out.finish_reason == "length"
    assert out.usage.total_tokens == 15
    assert out.usage.estimated_cost_usd is None  # self-hosted: never fabricated


def test_custom_without_api_key_sends_no_auth_header():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return _json({"model": "m", "choices": [{"message": {"content": "{}"}}]})

    adapter = CustomModelAdapter(
        base_url="http://localhost-ish.example:9999/v1",
        api_key=None,
        model="m",
        transport=httpx.MockTransport(handler),
    )
    import asyncio

    asyncio.run(adapter.generate(_request()))
    assert "Authorization" not in captured["headers"]


def test_custom_requires_base_url_and_model():
    import asyncio

    with pytest.raises(ProviderNotConfiguredError):
        asyncio.run(CustomModelAdapter(base_url=None, model="m").generate(_request()))
    with pytest.raises(ProviderNotConfiguredError):
        asyncio.run(
            CustomModelAdapter(base_url="http://x/v1", model=None).generate(_request())
        )


# ------------------------------------------------------- contract + isolation


def test_all_producers_return_same_normalized_contract():
    """Cloud / local / custom adapters all emit the SAME internal contract."""
    import asyncio

    openrouter = OpenRouterAdapter(
        api_key=KEY,
        model="or-m",
        transport=httpx.MockTransport(lambda r: _json(_openrouter_payload())),
    )
    ollama = OllamaAdapter(
        base_url="http://o:11434",
        model="ol-m",
        transport=httpx.MockTransport(
            lambda r: _json(
                {
                    "model": "ol-served",
                    "message": {"content": "{}"},
                    "done_reason": "stop",
                    "prompt_eval_count": 1,
                    "eval_count": 1,
                }
            )
        ),
    )
    custom = CustomModelAdapter(
        base_url="http://c/v1",
        model="cu-m",
        transport=httpx.MockTransport(
            lambda r: _json(
                {
                    "model": "cu-served",
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            )
        ),
    )
    outs = [
        asyncio.run(a.generate(_request(response_schema={"type": "object"})))
        for a in (openrouter, ollama, custom)
    ]
    for out in outs:
        assert type(out) is ModelResponse  # normalized contract ONLY
        assert out.provider.value in {"openrouter", "ollama", "custom"}
        assert out.requested_model is not None  # provenance present
        assert out.model  # served id present


def test_domain_layer_never_imports_provider_code():
    """Static isolation proof: domain/research modules must not reference
    provider adapters, HTTP clients, or provider names."""
    domain_files = [
        "services/fundamentals/research/agent.py",
        "services/fundamentals/research/critic.py",
        "services/fundamentals/context.py",
        "services/fundamentals/research/grounding.py",
        "services/fundamentals/research/evaluation.py",
        "apps/api/app/services/research_service.py",
        "apps/api/app/services/evaluation_service.py",
    ]
    # Import/dependency-focused: provider NAMES may appear in prose/docs, but
    # no adapter module, HTTP client, or adapter class may be referenced.
    forbidden = (
        "model_gateway.providers",
        "import httpx",
        "from httpx",
        "openrouteradapter",
        "ollamaadapter",
        "custommodeladapter",
        "anthropicadapter",
        "openaiadapter",
        "import openai",
        "import anthropic",
        "import ollama",
    )
    for rel in domain_files:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{rel} references {token!r}"


def test_evaluation_runner_is_provider_agnostic():
    """M2.2 runner evaluates openrouter/ollama/custom-labeled gateways over
    ONE context with zero provider-specific execution logic."""
    import asyncio

    from fundamentals.context import build_fundamental_context
    from fundamentals.providers.fixture import FixtureFundamentalsProvider
    from fundamentals.research.evaluation import ModelTarget, run_evaluation

    class _Gw:
        class ModelClass:
            REASONING = "reasoning"

        async def run(self, **kwargs):
            return {
                "content": None,
                "structured": {
                    "symbol": "ACME",
                    "research_timestamp": "2026-08-01T00:00:00+00:00",
                    "fundamental_view": "NEUTRAL",
                    "confidence": 0.5,
                    "investment_thesis": "probe",
                    "financial_assessment": {"area": "financial", "summary": "ok"},
                    "growth_assessment": {"area": "growth", "summary": "ok"},
                    "profitability_assessment": {"area": "profitability", "summary": "ok"},
                    "cash_flow_assessment": {"area": "cash_flow", "summary": "ok"},
                    "balance_sheet_assessment": {"area": "balance_sheet", "summary": "ok"},
                    "valuation_assessment": {"area": "valuation", "summary": "ok"},
                    "evidence": [],
                },
                "provider": "mock",
                "model": "mock-served",
                "latency_ms": 1,
            }

    fp = FixtureFundamentalsProvider()
    ctx = build_fundamental_context(
        "ACME",
        profile=fp.get_company_profile("ACME"),
        metrics=fp.get_financial_metrics("ACME"),
    )
    targets = [
        ModelTarget(provider="openrouter", model="cloud-m"),
        ModelTarget(provider="ollama", model="local-m"),
        ModelTarget(provider="custom", model="selfhosted-m"),
    ]
    from agents.events import EventSinkRegistry, RegistryEmitter

    result = asyncio.run(
        run_evaluation(
            "ACME",
            targets,
            emitter=RegistryEmitter(EventSinkRegistry()),
            context=ctx,
            gateway_factory=lambda t: _Gw(),
        )
    )
    assert [(r.provider, r.status) for r in result.records] == [
        ("openrouter", "completed"),
        ("ollama", "completed"),
        ("custom", "completed"),
    ]
    assert len({r.context_hash for r in result.records}) == 1  # identical context


def test_model_target_accepts_arbitrary_future_providers():
    from fundamentals.research.evaluation import ModelTarget

    t = ModelTarget(provider="future_agnostix_finetune", model="whatever-id")
    assert (t.provider, t.model) == ("future_agnostix_finetune", "whatever-id")
