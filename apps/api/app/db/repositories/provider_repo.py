"""Persistence operations for provider configurations and model targets."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProviderConfiguration, ProviderModelConfiguration


class ProviderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_visible(self, user_id: uuid.UUID) -> list[ProviderConfiguration]:
        stmt = (
            select(ProviderConfiguration)
            .where(
                (ProviderConfiguration.scope == "platform")
                | (
                    (ProviderConfiguration.scope == "user")
                    & (ProviderConfiguration.scope_id == user_id)
                )
            )
            .order_by(ProviderConfiguration.kind, ProviderConfiguration.provider)
        )
        return list((await self.session.scalars(stmt)).all())

    async def get_visible(
        self, provider_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProviderConfiguration | None:
        stmt = select(ProviderConfiguration).where(
            ProviderConfiguration.id == provider_id,
            (ProviderConfiguration.scope == "platform")
            | (
                (ProviderConfiguration.scope == "user")
                & (ProviderConfiguration.scope_id == user_id)
            ),
        )
        return await self.session.scalar(stmt)

    async def get_by_identity(
        self, *, kind: str, provider: str, scope: str, scope_id: uuid.UUID | None
    ) -> ProviderConfiguration | None:
        stmt = select(ProviderConfiguration).where(
            ProviderConfiguration.kind == kind,
            ProviderConfiguration.provider == provider,
            ProviderConfiguration.scope == scope,
            ProviderConfiguration.scope_id == scope_id,
        )
        return await self.session.scalar(stmt)

    async def models(self, configuration_id: uuid.UUID) -> list[ProviderModelConfiguration]:
        stmt = (
            select(ProviderModelConfiguration)
            .where(ProviderModelConfiguration.provider_configuration_id == configuration_id)
            .order_by(
                ProviderModelConfiguration.is_default.desc(), ProviderModelConfiguration.model
            )
        )
        return list((await self.session.scalars(stmt)).all())

    async def clear_default(self, configuration_id: uuid.UUID) -> None:
        await self.session.execute(
            update(ProviderModelConfiguration)
            .where(ProviderModelConfiguration.provider_configuration_id == configuration_id)
            .values(is_default=False)
        )

    async def delete(self, configuration: ProviderConfiguration) -> None:
        await self.session.delete(configuration)
