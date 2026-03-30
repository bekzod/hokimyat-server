"""
PDF Repository — data access layer for PDF documents.

Encapsulates all database operations for PDF records, keeping SQL
concerns out of the service layer.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import PDFNotFoundException
from models.pdf import PDF, PDFStatus


class PDFRepository:
    """Repository for PDF database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        file_id: str,
        employee_id: Optional[int] = None,
        employment_id: Optional[int] = None,
        doc_type: Optional[str] = None,
    ) -> PDF:
        """Create a new PDF record in processing state."""
        pdf_record = PDF(
            file_hash=file_id,
            uuid=file_id,
            status=PDFStatus.processing,
            employee_id=employee_id,
            employment_id=employment_id,
            doc_type=doc_type,
        )
        self.session.add(pdf_record)
        await self.session.flush()
        return pdf_record

    async def get_by_uuid(self, file_id: str) -> Optional[PDF]:
        """Get PDF record by UUID, or None if not found."""
        result = await self.session.execute(
            select(PDF).where(PDF.uuid == file_id)
        )
        return result.scalar_one_or_none()

    async def get_by_uuid_or_raise(self, file_id: str) -> PDF:
        """Get PDF record by UUID or raise PDFNotFoundException."""
        pdf = await self.get_by_uuid(file_id)
        if not pdf:
            raise PDFNotFoundException(file_id)
        return pdf

    async def delete_by_uuid(self, file_id: str) -> bool:
        """Delete PDF record by UUID. Returns True if deleted."""
        pdf_record = await self.get_by_uuid(file_id)
        if pdf_record:
            await self.session.delete(pdf_record)
            await self.session.flush()
            return True
        return False

    async def update_status(
        self,
        pdf: PDF,
        status: PDFStatus,
        error_message: Optional[str] = None,
    ) -> PDF:
        """Update PDF processing status."""
        pdf.status = status
        if error_message:
            pdf.error_message = error_message
        if status in (PDFStatus.completed, PDFStatus.failed):
            pdf.processed_at = datetime.now(timezone.utc)
        return pdf

    async def update_content(self, pdf: PDF, content: str, page_count: int) -> PDF:
        """Update PDF content and page count."""
        pdf.content = content
        pdf.total_page_count = page_count
        return pdf

    async def update_meta(self, pdf: PDF, meta: dict) -> PDF:
        """Update PDF metadata (AI extraction results)."""
        pdf.meta = meta
        return pdf

    async def update_manual_input(self, pdf: PDF, payload: dict) -> PDF:
        """Update manual input fields (user corrections)."""
        pdf.manual_input = pdf.manual_input or {}
        for field, field_data in payload.items():
            pdf.manual_input[field] = field_data
        pdf.updated_at = datetime.now(timezone.utc)
        return pdf

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()
