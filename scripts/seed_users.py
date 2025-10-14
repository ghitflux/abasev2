#!/usr/bin/env python
"""Seed initial users into the database."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Sequence

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.api.app.config import get_settings  # noqa: E402
from apps.api.app.db import AsyncSessionLocal  # noqa: E402
from apps.api.app.models import User  # noqa: E402
from apps.api.app.utils import hash_password  # noqa: E402

USERS: Sequence[dict[str, object]] = (
    {
        "email": "admin@abase.local",
        "full_name": "Administrador",
        "password": "admin123",
        "roles": ["ADMIN"],
    },
    {
        "email": "analista@abase.local",
        "full_name": "Analista",
        "password": "analista123",
        "roles": ["ANALISTA"],
    },
    {
        "email": "tesouraria@abase.local",
        "full_name": "Tesouraria",
        "password": "tesouraria123",
        "roles": ["TESOURARIA"],
    },
    {
        "email": "agente@abase.local",
        "full_name": "Agente",
        "password": "agente123",
        "roles": ["AGENTE"],
    },
)


async def seed() -> None:
    settings = get_settings()
    print(f"[seed] Using database: {settings.database_url}")

    async with AsyncSessionLocal() as session:
        for entry in USERS:
            email: str = entry["email"]  # type: ignore[assignment]
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                print(f"[seed] User {email} already exists, skipping")
                continue

            new_user = User(
                email=email,
                full_name=entry["full_name"],  # type: ignore[arg-type]
                password_hash=hash_password(str(entry["password"])),
                roles=list(entry["roles"]),  # type: ignore[arg-type]
            )
            session.add(new_user)
            print(f"[seed] Creating user {email}")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
