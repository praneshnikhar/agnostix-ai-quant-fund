"""Provider-management application service.

The service owns safe persistence, credential encryption, connection tests,
and model discovery. Runtime calls still use the existing ModelGateway and
M1 provider adapters; this module is not a replacement provider abstraction.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, cast

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.secrets import (
    decrypt_secret,
    encrypt_secret,
    mask_secret,
    require_provider_encryption_key,
)
from app.db.models import (
    AgentEvent,
    ProviderConfiguration,
    ProviderConnectionStatus,
    ProviderKind,
    ProviderModelConfiguration,
)
from app.db.repositories.provider_repo import ProviderRepository
from app.schemas.provider_management import (
    ConnectionTestOut,
    CredentialReplace,
    ModelConfigurationIn,
    ModelConfigurationOut,
    ModelDiscoveryOut,
    ProviderCreate,
    ProviderHealthOut,
    ProviderOut,
    ProviderUpdate,
)
from market_data.providers.alpaca_market_data import AlpacaMarketDataProvider
from market_data.providers.alpaca_news import AlpacaNewsProvider
from model_gateway.gateway import (
    get_model_gateway_for_configuration,
    known_providers,
)
from model_gateway.schemas import Message, ModelClass

AI_PROVIDERS = set(known_providers())
DATA_PROVIDERS = {"alpaca"}
DISCOVERY_PROVIDERS = {"openrouter", "openai", "ollama", "custom"}
DATA_CAPABILITIES = ["market_data", "news", "security_metadata", "trading"]


def _now() -> datetime:
    return datetime.now(UTC)


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Reject secret-looking metadata instead of persisting it accidentally."""
    forbidden = ("key", "secret", "token", "password", "authorization", "bearer")

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                if any(part in lowered for part in forbidden):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="metadata contains a prohibited credential field",
                    )
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for key in metadata:
        lowered = key.lower()
        if any(part in lowered for part in forbidden):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="metadata contains a prohibited credential field",
            )
    walk(metadata)
    return metadata


def _credentials_ciphertext(values: dict[str, str], key: str) -> str:
    return encrypt_secret(json.dumps(values, separators=(",", ":"), sort_keys=True), key)


def _credentials(configuration: ProviderConfiguration, key: str) -> dict[str, str]:
    if not configuration.secret_ciphertext:
        return {}
    raw = decrypt_secret(configuration.secret_ciphertext, key)
    data = json.loads(raw)
    return {str(name): str(value) for name, value in data.items() if value}


def _metadata(configuration: ProviderConfiguration) -> dict[str, Any]:
    return dict(configuration.metadata_json or {})


def _default_model(configuration: ProviderConfiguration) -> str | None:
    value = _metadata(configuration).get("default_model")
    return str(value) if value else None


def _feed(configuration: ProviderConfiguration) -> str | None:
    value = _metadata(configuration).get("market_data_feed")
    return str(value) if value else None


def _base_url(configuration: ProviderConfiguration) -> str | None:
    value = _metadata(configuration).get("base_url")
    return str(value) if value else None


def _error_status(exc: Exception) -> tuple[str, str, str]:
    if (
        "not configured" in str(exc).lower()
        or "credentials" in str(exc).lower()
        or "not set" in str(exc).lower()
    ):
        return "not_configured", "CONFIGURATION_INVALID", "Provider configuration is incomplete"
    if isinstance(exc, httpx.TimeoutException) or isinstance(exc, TimeoutError):
        return "timeout", "TIMEOUT", "Provider request timed out"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in {401, 403}:
            return "unauthorized", "INVALID_CREDENTIALS", "Provider rejected the credentials"
        if code == 404:
            return "failed", "MODEL_NOT_FOUND", "Provider resource was not found"
        if code >= 500:
            return "unavailable", "PROVIDER_UNAVAILABLE", "Provider is unavailable"
    return "failed", "PROVIDER_UNAVAILABLE", "Provider connection failed"


class ProviderManagementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProviderRepository(session)

    def _key(self) -> str:
        return require_provider_encryption_key(get_settings().provider_encryption_key)

    async def _audit(
        self, user_id: uuid.UUID, event_type: str, configuration_id: uuid.UUID
    ) -> None:
        self.session.add(
            AgentEvent(
                agent_id=f"user:{user_id}",
                event_type=event_type,
                payload={"provider_configuration_id": str(configuration_id)},
            )
        )

    async def _out(self, row: ProviderConfiguration) -> ProviderOut:
        key = self._key()
        values = _credentials(row, key)
        models = [
            ModelConfigurationOut.model_validate(model) for model in await self.repo.models(row.id)
        ]
        metadata = _metadata(row)
        health = ProviderHealthOut(**(row.health_json or {})) if row.health_json else None
        return ProviderOut(
            id=row.id,
            kind=cast(Literal["ai", "data"], row.kind),
            provider=row.provider,
            display_name=row.display_name,
            enabled=row.enabled,
            scope=cast(Literal["platform", "organization", "user"], row.scope),
            scope_id=row.scope_id,
            configured=bool(values),
            credential_status="configured" if values else "not_configured",
            masked_credential=mask_secret(values.get("api_key")),
            masked_secret=mask_secret(values.get("secret_key")),
            base_url=metadata.get("base_url"),
            market_data_feed=metadata.get("market_data_feed"),
            default_model=_default_model(row),
            connection_status=cast(
                Literal[
                    "unknown",
                    "connected",
                    "testing",
                    "failed",
                    "timeout",
                    "unauthorized",
                    "unavailable",
                    "not_configured",
                ],
                row.connection_status,
            ),
            last_tested_at=row.last_tested_at,
            metadata={
                k: v
                for k, v in metadata.items()
                if k not in {"base_url", "default_model", "market_data_feed"}
            },
            capabilities=DATA_CAPABILITIES if row.kind == ProviderKind.DATA.value else [],
            health=health,
            models=models,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_providers(self, user_id: uuid.UUID, kind: str) -> list[ProviderOut]:
        rows = [row for row in await self.repo.list_visible(user_id) if row.kind == kind]
        return [await self._out(row) for row in rows]

    async def get(self, user_id: uuid.UUID, kind: str, provider_id: uuid.UUID) -> ProviderOut:
        row = await self.repo.get_visible(provider_id, user_id)
        if row is None or row.kind != kind:
            raise HTTPException(status_code=404, detail="provider configuration not found")
        return await self._out(row)

    async def _get_row(
        self, user_id: uuid.UUID, kind: str, provider_id: uuid.UUID
    ) -> ProviderConfiguration:
        row = await self.repo.get_visible(provider_id, user_id)
        if row is None or row.kind != kind:
            raise HTTPException(status_code=404, detail="provider configuration not found")
        return row

    async def create(self, user_id: uuid.UUID, kind: str, request: ProviderCreate) -> ProviderOut:
        supported = AI_PROVIDERS if kind == ProviderKind.AI.value else DATA_PROVIDERS
        if request.provider not in supported:
            raise HTTPException(status_code=422, detail="unsupported provider")
        if request.scope == "organization":
            raise HTTPException(status_code=422, detail="organization scope is not configured")
        if request.scope == "user" and request.scope_id not in {None, user_id}:
            raise HTTPException(status_code=403, detail="provider scope is not owned by this user")
        scope_id = user_id if request.scope == "user" else request.scope_id
        if kind == ProviderKind.DATA.value and request.provider == "alpaca":
            if not request.api_key or not request.secret_key:
                raise HTTPException(
                    status_code=422, detail="Alpaca API and secret keys are required"
                )
            if request.base_url is not None:
                raise HTTPException(
                    status_code=422,
                    detail="Alpaca base URLs are not supported by the adapter contract",
                )
        if (
            kind == ProviderKind.AI.value
            and request.provider not in {"ollama"}
            and not request.api_key
        ):
            raise HTTPException(status_code=422, detail="provider API key is required")
        metadata = _safe_metadata(dict(request.metadata))
        for name, value in {
            "base_url": request.base_url,
            "default_model": request.default_model,
            "market_data_feed": request.market_data_feed,
        }.items():
            if value is not None:
                metadata[name] = value
        values = {
            k: v
            for k, v in {"api_key": request.api_key, "secret_key": request.secret_key}.items()
            if v
        }
        row = ProviderConfiguration(
            kind=kind,
            provider=request.provider,
            display_name=request.display_name,
            enabled=request.enabled,
            scope=request.scope,
            scope_id=scope_id,
            created_by=user_id,
            metadata_json=metadata,
            secret_ciphertext=_credentials_ciphertext(values, self._key()) if values else None,
            connection_status=ProviderConnectionStatus.UNKNOWN.value,
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise HTTPException(
                status_code=409, detail="provider configuration already exists"
            ) from exc
        if request.default_model and kind == ProviderKind.AI.value:
            self.session.add(
                ProviderModelConfiguration(
                    provider_configuration_id=row.id,
                    provider=row.provider,
                    model=request.default_model,
                    display_name=None,
                    is_default=True,
                    source="configured",
                )
            )
        await self._audit(user_id, "provider_created", row.id)
        await self.session.flush()
        return await self._out(row)

    async def update(
        self, user_id: uuid.UUID, kind: str, provider_id: uuid.UUID, request: ProviderUpdate
    ) -> ProviderOut:
        row = await self._get_row(user_id, kind, provider_id)
        data = request.model_dump(exclude_unset=True)
        if kind == ProviderKind.DATA.value and "base_url" in data:
            raise HTTPException(
                status_code=422, detail="Alpaca base URLs are not supported by the adapter contract"
            )
        metadata = _metadata(row)
        incoming = data.pop("metadata", None)
        if incoming is not None:
            metadata.update(_safe_metadata(incoming))
        for name in ("base_url", "default_model", "market_data_feed"):
            if name in data:
                value = data.pop(name)
                if value is None:
                    metadata.pop(name, None)
                else:
                    metadata[name] = value
        for name, value in data.items():
            setattr(row, name, value)
        row.metadata_json = metadata
        await self.session.flush()
        await self._audit(
            user_id,
            "provider_disabled" if data.get("enabled") is False else "provider_updated",
            row.id,
        )
        return await self._out(row)

    async def replace_credential(
        self, user_id: uuid.UUID, kind: str, provider_id: uuid.UUID, request: CredentialReplace
    ) -> ProviderOut:
        row = await self._get_row(user_id, kind, provider_id)
        values = _credentials(row, self._key())
        values["api_key"] = request.api_key
        if request.secret_key is not None:
            values["secret_key"] = request.secret_key
        row.secret_ciphertext = _credentials_ciphertext(values, self._key())
        row.credential_version += 1
        row.connection_status = ProviderConnectionStatus.UNKNOWN.value
        await self.session.flush()
        await self._audit(user_id, "provider_credential_replaced", row.id)
        return await self._out(row)

    async def delete(self, user_id: uuid.UUID, kind: str, provider_id: uuid.UUID) -> None:
        row = await self._get_row(user_id, kind, provider_id)
        await self._audit(user_id, "provider_deleted", row.id)
        await self.repo.delete(row)

    async def add_model(
        self, user_id: uuid.UUID, provider_id: uuid.UUID, request: ModelConfigurationIn
    ) -> ProviderOut:
        row = await self._get_row(user_id, ProviderKind.AI.value, provider_id)
        if request.is_default:
            await self.repo.clear_default(row.id)
            metadata = _metadata(row)
            metadata["default_model"] = request.model
            row.metadata_json = metadata
        model = ProviderModelConfiguration(
            provider_configuration_id=row.id,
            provider=row.provider,
            model=request.model,
            display_name=request.display_name,
            enabled=request.enabled,
            is_default=request.is_default,
            source="configured",
            metadata_json=_safe_metadata(request.metadata),
        )
        self.session.add(model)
        await self.session.flush()
        await self._audit(
            user_id, "default_model_changed" if request.is_default else "model_enabled", row.id
        )
        return await self._out(row)

    async def test(
        self, user_id: uuid.UUID, kind: str, provider_id: uuid.UUID
    ) -> ConnectionTestOut:
        row = await self._get_row(user_id, kind, provider_id)
        tested_at = _now()
        row.connection_status = ProviderConnectionStatus.TESTING.value
        await self.session.flush()
        values = _credentials(row, self._key())
        started = time.monotonic()
        capabilities: list[str] = []
        try:
            if kind == ProviderKind.AI.value:
                model = _default_model(row)
                if not model:
                    raise ValueError("model not configured")
                gateway = get_model_gateway_for_configuration(
                    row.provider,
                    model=model,
                    api_key=values.get("api_key"),
                    base_url=_base_url(row),
                )
                await gateway.run(
                    task="provider_connection_test",
                    model_class=ModelClass.CHEAP,
                    messages=[Message(role="user", content="Reply with OK.")],
                    max_tokens=4,
                )
            elif row.provider == "alpaca":
                if not values.get("api_key") or not values.get("secret_key"):
                    raise ValueError("credentials not configured")
                feed = _feed(row) or "iex"
                market = AlpacaMarketDataProvider(
                    api_key=values["api_key"], secret_key=values["secret_key"], feed=feed
                )
                await _to_thread(market.get_latest_quote, "AAPL")
                news = AlpacaNewsProvider(
                    api_key=values["api_key"], secret_key=values["secret_key"]
                )
                await _to_thread(news.get_news, ["AAPL"], 1)
                capabilities = DATA_CAPABILITIES
            else:
                raise ValueError("unsupported provider")
            status_value = ProviderConnectionStatus.CONNECTED.value
            code = None
            safe_error = None
        except Exception as exc:  # normalized below; never return provider detail
            status_value, code, safe_error = _error_status(exc)
        latency = int((time.monotonic() - started) * 1000)
        row.connection_status = status_value
        row.last_tested_at = tested_at
        await self.session.flush()
        await self._audit(user_id, "provider_connection_tested", row.id)
        return ConnectionTestOut(
            provider_id=row.id,
            provider=row.provider,
            status=cast(
                Literal[
                    "connected",
                    "failed",
                    "timeout",
                    "unauthorized",
                    "unavailable",
                    "not_configured",
                ],
                status_value,
            ),
            capabilities=capabilities,
            latency_ms=latency,
            last_tested_at=tested_at,
            error_code=code,
            error_safe=safe_error,
        )

    async def discover(self, user_id: uuid.UUID, provider_id: uuid.UUID) -> ModelDiscoveryOut:
        row = await self._get_row(user_id, ProviderKind.AI.value, provider_id)
        if row.provider not in DISCOVERY_PROVIDERS:
            return ModelDiscoveryOut(
                provider_id=row.id, provider=row.provider, status="unsupported"
            )
        values = _credentials(row, self._key())
        try:
            raw_models: list[dict[str, Any]] = await self._discover_http(row, values.get("api_key"))
        except Exception as exc:
            code = _error_status(exc)[1]
            return ModelDiscoveryOut(
                provider_id=row.id, provider=row.provider, status="failed", error_code=code
            )
        output: list[ModelConfigurationOut] = []
        for item in raw_models:
            existing = await self.session.scalar(
                select(ProviderModelConfiguration).where(
                    ProviderModelConfiguration.provider_configuration_id == row.id,
                    ProviderModelConfiguration.provider == row.provider,
                    ProviderModelConfiguration.model == item["model"],
                )
            )
            if existing is None:
                existing = ProviderModelConfiguration(
                    provider_configuration_id=row.id,
                    provider=row.provider,
                    model=item["model"],
                    display_name=item.get("display_name"),
                    capabilities=item.get("capabilities"),
                    context_window=item.get("context_window"),
                    source="discovery",
                    available=True,
                    metadata_json=item.get("metadata"),
                )
                self.session.add(existing)
            else:
                existing.available = True
                existing.source = "discovery"
                existing.metadata_json = item.get("metadata")
            await self.session.flush()
            output.append(ModelConfigurationOut.model_validate(existing))
        await self._audit(user_id, "model_discovered", row.id)
        return ModelDiscoveryOut(
            provider_id=row.id, provider=row.provider, status="supported", models=output
        )

    async def _discover_http(
        self, row: ProviderConfiguration, api_key: str | None
    ) -> list[dict[str, Any]]:
        default_urls = {
            "openrouter": "https://openrouter.ai/api/v1",
            "openai": "https://api.openai.com/v1",
        }
        base = _base_url(row) or default_urls.get(row.provider)
        if row.provider == "ollama":
            endpoint = f"{base or 'http://localhost:11434'}/api/tags"
        else:
            if not base:
                raise ValueError("base URL not configured")
            endpoint = f"{base.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(endpoint, headers=headers)
            response.raise_for_status()
            payload = response.json()
        rows = payload.get("models", []) if row.provider == "ollama" else payload.get("data", [])
        result: list[dict[str, Any]] = []
        for item in rows or []:
            model = str(item.get("name") or item.get("id") or "").strip()
            if not model:
                continue
            result.append(
                {
                    "model": model,
                    "display_name": item.get("name") or item.get("id"),
                    "context_window": item.get("context_length")
                    if isinstance(item.get("context_length"), int)
                    else None,
                    "capabilities": None,
                    "metadata": {"owned_by": item.get("owned_by")}
                    if item.get("owned_by")
                    else None,
                }
            )
        return result


async def _to_thread(function, *args):
    import asyncio

    return await asyncio.to_thread(function, *args)
