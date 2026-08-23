"""Deterministic M2.5 provider-management security and contract tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from app.core.auth import _verify_token, issue_access_token
from app.core.secrets import decrypt_secret, encrypt_secret, mask_secret
from app.db.models import ProviderConfiguration, ProviderKind
from app.db.repositories.provider_repo import ProviderRepository
from app.db.session import AsyncSession
from app.services import provider_management as management
from model_gateway.gateway import get_model_gateway_for_configuration

KEY = "sk-provider-management-test-key"


@pytest.fixture
def fernet_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def test_secret_encryption_roundtrip_and_mask(fernet_key: str) -> None:
    ciphertext = encrypt_secret(KEY, fernet_key)
    assert ciphertext != KEY
    assert KEY not in ciphertext
    assert decrypt_secret(ciphertext, fernet_key) == KEY
    assert mask_secret(KEY) == "••••••••-key"


def test_provider_model_has_separate_ciphertext_column() -> None:
    columns = {column.name for column in ProviderConfiguration.__table__.columns}
    assert "secret_ciphertext" in columns
    assert "metadata_json" in columns
    assert "api_key" not in columns


def test_provider_metadata_rejects_nested_secrets() -> None:
    with pytest.raises(Exception, match="credential"):
        management._safe_metadata({"headers": {"Authorization": "Bearer secret"}})


def test_auth_token_is_bound_to_existing_user_id() -> None:
    user_id = uuid.uuid4()
    token = issue_access_token(user_id, "auth-test-secret")
    assert _verify_token(token, "auth-test-secret") == user_id
    assert _verify_token(token, "wrong-secret") is None


def test_gateway_configuration_uses_existing_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        management,
        "get_settings",
        lambda: SimpleNamespace(
            provider_encryption_key="unused",
            ollama_timeout_seconds=30.0,
            openrouter_timeout_seconds=30.0,
            custom_model_timeout_seconds=30.0,
        ),
    )
    gateway = get_model_gateway_for_configuration(
        "openrouter", api_key=KEY, model="openrouter/free"
    )
    adapter = gateway._adapters["openrouter"]
    assert adapter.api_key == KEY
    assert list(gateway._adapters) == ["openrouter"]


@pytest.mark.asyncio
async def test_safe_provider_response_never_returns_plaintext_secret(
    monkeypatch: pytest.MonkeyPatch, fernet_key: str
) -> None:
    row = ProviderConfiguration(
        id=uuid.uuid4(),
        kind=ProviderKind.DATA.value,
        provider="alpaca",
        display_name="Research Alpaca",
        enabled=True,
        scope="platform",
        created_by=uuid.uuid4(),
        metadata_json={"market_data_feed": "iex"},
        secret_ciphertext=encrypt_secret(
            '{"api_key":"' + KEY + '","secret_key":"secret-value"}', fernet_key
        ),
        connection_status="unknown",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(
        management,
        "get_settings",
        lambda: SimpleNamespace(provider_encryption_key=fernet_key),
    )
    service = management.ProviderManagementService(cast(AsyncSession, SimpleNamespace()))
    service.repo = cast(ProviderRepository, SimpleNamespace(models=lambda _id: _empty_models()))
    response = await service._out(row)
    payload = response.model_dump_json()
    assert KEY not in payload
    assert "secret-value" not in payload
    assert response.masked_credential == "••••••••-key"
    assert response.masked_secret == "•" * 8 + "alue"


async def _empty_models() -> list:
    return []


def test_ai_and_data_provider_categories_are_distinct() -> None:
    assert ProviderKind.AI.value != ProviderKind.DATA.value
    assert "trading" not in management.AI_PROVIDERS
    assert management.DATA_PROVIDERS == {"alpaca"}
