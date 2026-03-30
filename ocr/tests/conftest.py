"""
Test configuration and shared fixtures.

Sets up:
- SQLite async engine for isolated DB tests
- Mock MinIO storage
- FastAPI test client with dependency overrides
"""

import os

# Required env vars — set BEFORE any project imports so that
# core.config.Settings validation and core.database engine creation
# don't fail. These values are never actually connected to;
# tests use an in-memory SQLite DB instead.
os.environ.setdefault(
    "OCR_SERVER_DATABASE_URL", "postgresql://test:test@localhost/test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("OPENAI_API_BASE_URL", "http://localhost:8000/v1")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from core.database import Base
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from repositories.document_repository import DocumentRepository
from services.document_service import DocumentService
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ── Database fixtures ──────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    """Create a fresh in-memory SQLite engine with all tables per test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Yield an async session for repository / service tests."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── Mock fixtures ──────────────────────────────────────────────


@pytest.fixture
def mock_storage():
    """Mock MinIO storage — every method is an async no-op."""
    storage = AsyncMock()
    storage.upload_fileobj = AsyncMock(return_value="test-file-id")
    storage.generate_presigned_url = AsyncMock(return_value="http://test/file")
    storage.delete_file = AsyncMock(return_value=True)
    return storage


# ── API test client ────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(db_engine, mock_storage):
    """
    Async HTTP client backed by a test FastAPI app.

    - DB: in-memory SQLite (via db_engine)
    - Storage: AsyncMock (no real MinIO)
    - Celery: process_document_task.apply_async is a no-op MagicMock
    """
    from api import deps
    from api.v1.router import api_router

    # Build a minimal test app (skips static files mount from main.py)
    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    # Override the DocumentService dependency to use test DB + mock storage
    async def override_get_document_service():
        async with factory() as session:
            repo = DocumentRepository(session)
            service = DocumentService(repository=repo, storage=mock_storage)
            try:
                yield service
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[deps.get_document_service] = override_get_document_service

    # Patch Celery task to prevent real task dispatch
    with patch("api.v1.endpoints.upload.process_document_task") as mock_task:
        mock_task.apply_async = MagicMock()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Expose mock for assertions in tests
            ac.mock_task = mock_task  # type: ignore[attr-defined]
            yield ac
