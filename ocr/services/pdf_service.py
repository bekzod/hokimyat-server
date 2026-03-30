"""
PDF Service — high-level PDF operations orchestration.

Handles document upload/validation, status retrieval, and manual metadata updates.
"""

import logging
import uuid
from typing import Optional

from fastapi import UploadFile

from core.exceptions import ValidationException, StorageException
from core.storage import MinIOStorage, get_storage
from models.pdf import PDF
from repositories.pdf_repository import PDFRepository

logger = logging.getLogger(__name__)

# Allowed MIME types for document upload
ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/markdown",
    "text/asciidoc",
    "text/html",
    "application/xhtml+xml",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
]


class PDFService:
    """Orchestrates file upload, storage, and database operations."""

    def __init__(
        self,
        repository: PDFRepository,
        storage: Optional[MinIOStorage] = None,
    ):
        self.repository = repository
        self.storage = storage or get_storage()

    @staticmethod
    def generate_file_id() -> str:
        """Generate a unique file identifier (UUID v4)."""
        return str(uuid.uuid4())

    @staticmethod
    def validate_file_type(content_type: Optional[str]) -> None:
        """Validate that the file type is allowed. Raises ValidationException if not."""
        if not content_type or content_type not in ALLOWED_MIME_TYPES:
            raise ValidationException(
                f"Invalid file type: {content_type}. "
                f"Allowed types: PDF, DOCX, XLSX, PPTX, Markdown, HTML, CSV, Images"
            )

    @staticmethod
    def validate_uuid(file_id: str) -> None:
        """Validate that file_id is a valid UUID."""
        try:
            uuid.UUID(file_id)
        except ValueError:
            raise ValidationException(f"Invalid file ID: {file_id}")

    @staticmethod
    def validate_manual_update_payload(payload: dict) -> None:
        """Validate manual update payload — each field needs old, new, description."""
        for field, field_data in payload.items():
            if not isinstance(field_data, dict) or not all(
                key in field_data for key in ("old", "new", "description")
            ):
                raise ValidationException(
                    f"Invalid data for field: {field}. "
                    f"Each field must have 'old', 'new', and 'description' keys."
                )

    async def upload_document(
        self,
        file: UploadFile,
        employee_id: Optional[int] = None,
        employment_id: Optional[int] = None,
        doc_type: Optional[str] = None,
    ) -> PDF:
        """Upload document: validate, create DB record, store file."""
        self.validate_file_type(file.content_type)

        file_id = self.generate_file_id()

        logger.info(
            f"Processing upload: file_id={file_id}, "
            f"filename={file.filename}, content_type={file.content_type}"
        )

        # Create database record first
        pdf_record = await self.repository.create(
            file_id=file_id,
            employee_id=employee_id,
            employment_id=employment_id,
            doc_type=doc_type,
        )

        # Upload to storage — rollback DB record on failure
        try:
            metadata = {
                "employee_id": str(employee_id) if employee_id else "",
                "employment_id": str(employment_id) if employment_id else "",
                "doc_type": doc_type or "",
                "filename": file.filename or "",
            }
            await self.storage.upload_fileobj(
                file_obj=file.file,
                file_id=file_id,
                content_type=file.content_type or "application/octet-stream",
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to upload file {file_id}: {e}")
            await self.repository.delete_by_uuid(file_id)
            raise StorageException(f"Failed to upload file: {e}", original_error=e)

        logger.info(f"Successfully uploaded file: {file_id}")
        return pdf_record

    async def get_status(self, file_id: str) -> PDF:
        """Get PDF processing status. Raises PDFNotFoundException if not found."""
        return await self.repository.get_by_uuid_or_raise(file_id)

    async def update_manual_input(self, file_id: str, payload: dict) -> PDF:
        """Update manual input for PDF. Validates inputs first."""
        self.validate_uuid(file_id)
        self.validate_manual_update_payload(payload)

        pdf = await self.repository.get_by_uuid_or_raise(file_id)
        await self.repository.update_manual_input(pdf, payload)

        logger.info(f"Updated manual input for file: {file_id}")
        return pdf
