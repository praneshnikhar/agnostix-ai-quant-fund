"""Public provider-management API contracts. Secrets never appear here."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProviderKind = Literal["ai", "data"]
ProviderScope = Literal["platform", "organization", "user"]
ConnectionStatus = Literal[
    "unknown",
    "connected",
    "testing",
    "failed",
    "timeout",
    "unauthorized",
    "unavailable",
    "not_configured",
]


class ProviderCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=160)
    enabled: bool = True
    scope: ProviderScope = "platform"
    scope_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    base_url: str | None = Field(default=None, max_length=2048)
    default_model: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    secret_key: str | None = Field(default=None, min_length=1, max_length=4096)
    market_data_feed: Literal["iex", "sip"] | None = None

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()


class ProviderUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None
    base_url: str | None = Field(default=None, max_length=2048)
    default_model: str | None = Field(default=None, max_length=512)
    market_data_feed: Literal["iex", "sip"] | None = None


class CredentialReplace(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)
    secret_key: str | None = Field(default=None, min_length=1, max_length=4096)


class ModelConfigurationIn(BaseModel):
    model: str = Field(min_length=1, max_length=512)
    display_name: str | None = Field(default=None, max_length=160)
    enabled: bool = True
    is_default: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelConfigurationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    model: str
    display_name: str | None
    enabled: bool
    is_default: bool
    capabilities: list[str] | None
    context_window: int | None
    source: str
    available: bool | None
    metadata: dict[str, Any] | None


class ProviderHealthOut(BaseModel):
    last_successful_ingestion: datetime | None = None
    freshness: Literal["fresh", "stale", "missing", "invalid"] | None = None
    provider_latency_ms: int | None = None
    data_quality: Literal["fresh", "stale", "missing", "invalid"] | None = None
    last_error_safe: str | None = None
    available_feeds: list[str] | None = None
    symbols_covered: int | None = None


class ProviderOut(BaseModel):
    id: uuid.UUID
    kind: ProviderKind
    provider: str
    display_name: str
    enabled: bool
    scope: ProviderScope
    scope_id: uuid.UUID | None
    configured: bool
    credential_status: Literal["configured", "not_configured"]
    masked_credential: str | None
    masked_secret: str | None
    base_url: str | None
    market_data_feed: str | None
    default_model: str | None
    connection_status: ConnectionStatus
    last_tested_at: datetime | None
    metadata: dict[str, Any]
    capabilities: list[str]
    health: ProviderHealthOut | None
    models: list[ModelConfigurationOut]
    created_at: datetime
    updated_at: datetime


class ConnectionTestOut(BaseModel):
    provider_id: uuid.UUID
    provider: str
    status: Literal[
        "connected", "failed", "timeout", "unauthorized", "unavailable", "not_configured"
    ]
    capabilities: list[str]
    latency_ms: int | None = None
    last_tested_at: datetime
    error_code: str | None = None
    error_safe: str | None = None


class ModelDiscoveryOut(BaseModel):
    provider_id: uuid.UUID
    provider: str
    status: Literal["supported", "unsupported", "failed"]
    models: list[ModelConfigurationOut] = Field(default_factory=list)
    error_code: str | None = None
