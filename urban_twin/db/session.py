from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from urban_twin.config import settings


def _asyncpg_connect_args(url: str) -> dict:
    """PgBouncer (Supabase transaction pooler) cannot use prepared statements."""
    host = url.lower()
    if "pooler.supabase.com" in host or ":6543/" in host:
        return {"statement_cache_size": 0}
    return {}


async_engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=_asyncpg_connect_args(settings.database_url),
)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_session() -> Session:
    return SyncSessionLocal()
