"""Seed script — creates the initial admin user.

Run: `python -m db.seeds.seed` (requires a migrated PostgreSQL database).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from sqlalchemy import select  # noqa: E402

from app.db.models import User, UserRole  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402


async def seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        existing = await session.execute(select(User).where(User.role == UserRole.ADMIN.value))
        if existing.scalars().first() is not None:
            print("Admin user already exists; nothing to do.")
            return

        session.add(
            User(
                name="Fund Admin",
                role=UserRole.ADMIN.value,
                is_active=True,
            )
        )
        await session.commit()
        print("Seeded admin user.")


if __name__ == "__main__":
    asyncio.run(seed())