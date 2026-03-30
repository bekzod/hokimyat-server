"""
Document Repository — data access layer for documents.

Encapsulates all database operations for document records, keeping SQL
concerns out of the service layer.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DocumentNotFoundException
from models.pdf import Document, DocumentStatus


class DocumentRepository:
    """Repository for document database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        file_id: str,
    ) -> Document:
        """Create a new document record in processing state."""
        record = Document(
            file_hash=file_id,
            uuid=file_id,
            status=DocumentStatus.processing,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_uuid(self, file_id: str) -> Optional[Document]:
        """Get document record by UUID, or None if not found."""
        result = await self.session.execute(
            select(Document).where(Document.uuid == file_id)
        )
        return result.scalar_one_or_none()

    async def get_by_uuid_or_raise(self, file_id: str) -> Document:
        """Get document record by UUID or raise DocumentNotFoundException."""
        doc = await self.get_by_uuid(file_id)
        if not doc:
            raise DocumentNotFoundException(file_id)
        return doc

    async def delete_by_uuid(self, file_id: str) -> bool:
        """Delete document record by UUID. Returns True if deleted."""
        record = await self.get_by_uuid(file_id)
        if record:
            await self.session.delete(record)
            await self.session.flush()
            return True
        return False

    async def update_status(
        self,
        doc: Document,
        status: DocumentStatus,
        error_message: Optional[str] = None,
    ) -> Document:
        """Update document processing status."""
        doc.status = status
        if error_message:
            doc.error_message = error_message
        if status in (DocumentStatus.completed, DocumentStatus.failed):
            doc.processed_at = datetime.now(timezone.utc)
        return doc

    async def update_content(self, doc: Document, content: str, page_count: int) -> Document:
        """Update document content and page count."""
        doc.content = content
        doc.total_page_count = page_count
        return doc

    async def update_meta(self, doc: Document, meta: dict) -> Document:
        """Update document metadata (AI extraction results)."""
        doc.meta = meta
        return doc

    async def update_manual_input(self, doc: Document, payload: dict) -> Document:
        """Update manual input fields (user corrections)."""
        doc.manual_input = doc.manual_input or {}
        for field, field_data in payload.items():
            doc.manual_input[field] = field_data
        doc.updated_at = datetime.now(timezone.utc)
        return doc

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()
