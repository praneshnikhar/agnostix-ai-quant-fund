"""Authenticated provider-management API.

AI and data providers share configuration persistence, but their runtime
boundaries remain distinct: ModelGateway for AI and M1 adapters for data.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    CurrentUser,
    require_provider_delete,
    require_provider_read,
    require_provider_write,
)
from app.db.session import get_session
from app.schemas.provider_management import (
    ConnectionTestOut,
    CredentialReplace,
    ModelConfigurationIn,
    ModelDiscoveryOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
)
from app.services.provider_management import ProviderManagementService

router = APIRouter(prefix="/provider-configurations", tags=["provider-management"])


def _service(session: AsyncSession) -> ProviderManagementService:
    return ProviderManagementService(session)


@router.get("/ai", response_model=list[ProviderOut])
async def list_ai_providers(
    user: CurrentUser = Depends(require_provider_read),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderOut]:
    return await _service(session).list_providers(user.id, "ai")


@router.post("/ai", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_ai_provider(
    request: ProviderCreate,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).create(user.id, "ai", request)


@router.get("/ai/{provider_id}", response_model=ProviderOut)
async def get_ai_provider(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(require_provider_read),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).get(user.id, "ai", provider_id)


@router.patch("/ai/{provider_id}", response_model=ProviderOut)
async def update_ai_provider(
    provider_id: uuid.UUID,
    request: ProviderUpdate,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).update(user.id, "ai", provider_id, request)


@router.delete("/ai/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_provider(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(require_provider_delete),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _service(session).delete(user.id, "ai", provider_id)


@router.post("/ai/{provider_id}/credentials", response_model=ProviderOut)
async def replace_ai_credentials(
    provider_id: uuid.UUID,
    request: CredentialReplace,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).replace_credential(user.id, "ai", provider_id, request)


@router.post("/ai/{provider_id}/test", response_model=ConnectionTestOut)
async def test_ai_provider(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ConnectionTestOut:
    return await _service(session).test(user.id, "ai", provider_id)


@router.post("/ai/{provider_id}/models", response_model=ProviderOut)
async def add_ai_model(
    provider_id: uuid.UUID,
    request: ModelConfigurationIn,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).add_model(user.id, provider_id, request)


@router.post("/ai/{provider_id}/models/discover", response_model=ModelDiscoveryOut)
async def discover_ai_models(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ModelDiscoveryOut:
    return await _service(session).discover(user.id, provider_id)


@router.get("/data", response_model=list[ProviderOut])
async def list_data_providers(
    user: CurrentUser = Depends(require_provider_read),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderOut]:
    return await _service(session).list_providers(user.id, "data")


@router.post("/data", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_data_provider(
    request: ProviderCreate,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).create(user.id, "data", request)


@router.get("/data/{provider_id}", response_model=ProviderOut)
async def get_data_provider(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(require_provider_read),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).get(user.id, "data", provider_id)


@router.patch("/data/{provider_id}", response_model=ProviderOut)
async def update_data_provider(
    provider_id: uuid.UUID,
    request: ProviderUpdate,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).update(user.id, "data", provider_id, request)


@router.delete("/data/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_provider(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(require_provider_delete),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _service(session).delete(user.id, "data", provider_id)


@router.post("/data/{provider_id}/credentials", response_model=ProviderOut)
async def replace_data_credentials(
    provider_id: uuid.UUID,
    request: CredentialReplace,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return await _service(session).replace_credential(user.id, "data", provider_id, request)


@router.post("/data/{provider_id}/test", response_model=ConnectionTestOut)
async def test_data_provider(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(require_provider_write),
    session: AsyncSession = Depends(get_session),
) -> ConnectionTestOut:
    return await _service(session).test(user.id, "data", provider_id)
