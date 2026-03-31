"""
Document Service — business logic for document operations.

Orchestrates repository and storage operations, handles validation.
"""

import logging
import uuid as uuid_mod

from core.exceptions import StorageException, ValidationException
from repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentService:
    """Service layer for document upload, status, and manual updates."""

    def __init__(self, repository: DocumentRepository, storage):
        self.repository = repository
        self.storage = storage

    # ── Static validation helpers ──────────────────────────────

    @staticmethod
    def validate_file_type(content_type: str | None) -> None:
        if not content_type or content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationException(
                f"Unsupported file type: {content_type}"
            )

    @staticmethod
    def validate_uuid(file_id: str) -> None:
        try:
            uuid_mod.UUID(file_id, version=4)
        except (ValueError, AttributeError):
            raise ValidationException(f"Invalid UUID: {file_id}")

    @staticmethod
    def validate_manual_update_payload(payload: dict) -> None:
        for field_name, field_data in payload.items():
            if not isinstance(field_data, dict):
                raise ValidationException(
                    f"Field '{field_name}' must be a dict with old/new/description"
                )
            required = {"old", "new", "description"}
            if not required.issubset(field_data.keys()):
                raise ValidationException(
                    f"Field '{field_name}' missing required keys: {required - field_data.keys()}"
                )

    @staticmethod
    def generate_file_id() -> str:
        return str(uuid_mod.uuid4())

    # ── Instance methods ───────────────────────────────────────

    async def upload_document(self, file) -> "Document":  # noqa: F821
        """Validate, store, and create DB record for an uploaded file."""
        self.validate_file_type(file.content_type)

        file_id = self.generate_file_id()

        try:
            await self.storage.upload_fileobj(
                file.file,
                file_id,
                content_type=file.content_type or "application/octet-stream",
                metadata={"original_filename": file.filename or "unknown"},
            )
        except Exception as e:
            raise StorageException("Failed to upload file", original_error=e)

        record = await self.repository.create(file_id=file_id)
        await self.repository.commit()
        return record

    async def get_status(self, file_id: str):
        """Get document record by ID (raises if not found)."""
        self.validate_uuid(file_id)
        return await self.repository.get_by_uuid_or_raise(file_id)

    async def list_recent(self, limit: int = 50, offset: int = 0):
        """List recent documents."""
        return await self.repository.list_recent(limit=limit, offset=offset)

    async def delete_document(self, file_id: str) -> bool:
        """Delete a document by ID."""
        self.validate_uuid(file_id)
        deleted = await self.repository.delete_by_uuid(file_id)
        if deleted:
            await self.repository.commit()
        return deleted

    async def update_manual_input(self, file_id: str, payload: dict):
        """Apply manual corrections to document metadata."""
        self.validate_uuid(file_id)
        self.validate_manual_update_payload(payload)

        doc = await self.repository.get_by_uuid_or_raise(file_id)
        doc = await self.repository.update_manual_input(doc, payload)
        await self.repository.commit()
        return doc
