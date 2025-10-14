from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from .config import get_settings


def _build_async_database_url(url: str) -> str:
    """Ensure the database URL is using an async driver."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Base(DeclarativeBase):
    """Base declarative model."""


settings = get_settings()
DATABASE_URL = _build_async_database_url(settings.database_url)

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.environment == "development",
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Validate that the database connection can be established."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


@asynccontextmanager
async def lifespan_session() -> AsyncIterator[AsyncSession]:
    """Provide a session for FastAPI lifespan events."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for DB access."""
    async with AsyncSessionLocal() as session:
        yield session
