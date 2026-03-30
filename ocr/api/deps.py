"""
API Dependencies — shared FastAPI dependency injection.

These are injected into route handlers via Depends().
"""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.storage import get_storage
from repositories.pdf_repository import PDFRepository
from services.pdf_service import PDFService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the request lifecycle."""
    async for session in get_async_db():
        yield session


async def get_pdf_repository(
    db: AsyncSession = Depends(get_db),
) -> PDFRepository:
    """Get PDF repository instance with the request's DB session."""
    return PDFRepository(db)


async def get_pdf_service(
    repository: PDFRepository = Depends(get_pdf_repository),
) -> PDFService:
    """Get PDF service instance with injected repository and storage."""
    return PDFService(repository=repository, storage=get_storage())
