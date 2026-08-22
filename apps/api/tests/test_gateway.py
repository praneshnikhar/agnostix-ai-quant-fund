"""Model gateway tests — routing, telemetry, and no-provider failure.

Uses fake adapters; no real LLM calls (CI must never depend on providers).
"""

from __future__ import annotations

import uuid

import pytest

from model_gateway.gateway import ModelGateway, NoProviderConfiguredError
from model_gateway.providers.base import ProviderAdapter
from model_gateway.schemas import (
    Message,
    ModelClass,
    ModelRequest,
    ModelResponse,
    ProviderName,
)


class FakeAdapter(ProviderAdapter):
    def __init__(self, name: str, configured: bool) -> None:
        super().__init__(api_key="fake" if configured else None)
        self.name = name
        self._configured = configured

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            request_id=uuid.uuid4(),
            provider=ProviderName.OPENAI,  # arbitrary for the fake
            model=f"{self.name}-model",
            content="ok",
            latency_ms=1,
        )


def _msg() -> list[Message]:
    return [Message(role="user", content="hello")]


async def test_routes_to_first_configured_provider() -> None:
    gateway = ModelGateway(
        adapters=[
            FakeAdapter("anthropic", configured=False),
            FakeAdapter("openai", configured=True),
        ]
    )
    resp = await gateway.run(task="test", model_class=ModelClass.STANDARD, messages=_msg())
    assert resp.success is True
    assert resp.model == "openai-model"
    assert len(gateway.telemetry.snapshot()) == 1


async def test_no_provider_configured_raises() -> None:
    gateway = ModelGateway(adapters=[FakeAdapter("anthropic", configured=False)])
    with pytest.raises(NoProviderConfiguredError):
        await gateway.run(task="test", model_class=ModelClass.REASONING, messages=_msg())


async def test_telemetry_records_failure_then_raises() -> None:
    class ExplodingAdapter(FakeAdapter):
        async def generate(self, request: ModelRequest) -> ModelResponse:
            raise RuntimeError("boom")

    gateway = ModelGateway(adapters=[ExplodingAdapter("openai", True)])
    with pytest.raises(RuntimeError):
        await gateway.run(task="test", model_class=ModelClass.CHEAP, messages=_msg())
    snap = gateway.telemetry.snapshot()
    assert len(snap) == 1
    assert snap[0].success is False
    assert snap[0].error is not None


async def test_embedding_prefers_local_provider() -> None:
    gateway = ModelGateway(
        adapters=[
            FakeAdapter("anthropic", True),
            FakeAdapter("ollama", True),
        ],
        routing_preference=["anthropic", "ollama"],
    )
    resp = await gateway.run(task="embed", model_class=ModelClass.EMBEDDING, messages=_msg())
    assert resp.model == "ollama-model"
