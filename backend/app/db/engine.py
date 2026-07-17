"""Async SQLAlchemy engine, built from Config.database_url."""
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import DATABASE_URL


def _to_async_dsn(url: str) -> str:
    """Rewrite a plain postgresql:// DSN to use the asyncpg driver."""
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine: AsyncEngine = create_async_engine(_to_async_dsn(DATABASE_URL), pool_pre_ping=True)
