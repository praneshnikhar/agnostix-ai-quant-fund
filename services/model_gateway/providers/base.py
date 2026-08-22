"""Provider adapter interface.

Each adapter translates the gateway's typed ModelRequest into a
provider-specific API call. Adapters must never be imported by agents —
only the gateway uses them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from model_gateway.schemas import ModelRequest, ModelResponse


class ProviderNotConfiguredError(RuntimeError):
    """Raised when a provider lacks required credentials/configuration."""


class ProviderAdapter(ABC):
    """Base class for all provider adapters."""

    name: str

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url

    @property
    def is_configured(self) -> bool:
        """Whether this provider has the credentials it needs."""
        raise NotImplementedError

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Execute a completion request and return a typed response."""
        ...
