"""
Async database configuration using SQLAlchemy with asyncpg.

Provides the async engine, session factory, and declarative base
used by the ORM models and repository layer.
"""

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from .config import get_settings


def _get_async_database_url() -> str:
    """Convert database URL to async-compatible format (postgresql+asyncpg://)."""
    settings = get_settings()
    url = settings.ocr_server_database_url

    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://")
    return url


# Async engine — NullPool avoids connection reuse across event loops
async_engine = create_async_engine(
    _get_async_database_url(),
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

metadata = MetaData()
Base = declarative_base(metadata=metadata)


async def get_async_db():
    """Yield an AsyncSession; auto-commits on success, rolls back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_async_session() -> AsyncSession:
    """Get a standalone async session for use outside of request context."""
    return AsyncSessionLocal()
