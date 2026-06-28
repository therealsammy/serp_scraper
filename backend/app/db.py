"""Async SQLAlchemy engine/session and Redis client."""
from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings


def _async_db_url(url: str) -> str:
    """Normalize managed-Postgres URLs (Render/Neon/Supabase give postgres://
    or postgresql://) to the async driver SQLAlchemy needs."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _engine_kwargs(url: str) -> dict:
    """Remote managed Postgres (Supabase/Neon) requires TLS; asyncpg needs an SSL
    context via connect_args. Supabase's pooler presents a cert our container's CA
    bundle doesn't fully trust, so encrypt without chain verification. Skip for
    local docker-compose."""
    host_is_local = "localhost" in url or "127.0.0.1" in url or "@db:" in url
    if host_is_local:
        return {}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return {"connect_args": {"ssl": ctx}}


_db_url = _async_db_url(settings.database_url)
engine = create_async_engine(_db_url, pool_pre_ping=True, **_engine_kwargs(_db_url))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

redis_client: aioredis.Redis = aioredis.from_url(
    settings.redis_url, encoding="utf-8", decode_responses=True
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def get_redis() -> aioredis.Redis:
    return redis_client


async def init_db() -> None:
    """Create tables on startup (simple bootstrap; swap for Alembic in prod)."""
    from . import models  # noqa: F401 — ensure models are registered

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
