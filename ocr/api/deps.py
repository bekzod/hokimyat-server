"""
API Dependencies — shared FastAPI dependency injection.

These are injected into route handlers via Depends().
"""

from typing import AsyncGenerator

from core.database import get_async_db
from core.storage import get_storage
from fastapi import Depends
from repositories.document_repository import DocumentRepository
from services.document_service import DocumentService
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the request lifecycle."""
    async for session in get_async_db():
        yield session


async def get_document_repository(
    db: AsyncSession = Depends(get_db),
) -> DocumentRepository:
    """Get document repository instance with the request's DB session."""
    return DocumentRepository(db)


async def get_document_service(
    repository: DocumentRepository = Depends(get_document_repository),
) -> DocumentService:
    """Get document service instance with injected repository and storage."""
    return DocumentService(repository=repository, storage=get_storage())
