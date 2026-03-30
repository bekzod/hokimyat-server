"""
Tests for DocumentRepository — async CRUD against in-memory SQLite.

Each test gets a fresh database via the db_session fixture,
so tests are fully isolated from each other.
"""

import pytest
from core.exceptions import DocumentNotFoundException
from models.pdf import DocumentStatus
from repositories.document_repository import DocumentRepository

# ── Helper ─────────────────────────────────────────────────────


async def _create_record(repo: DocumentRepository, file_id: str = "test-uuid-1"):
    """Shortcut to create a document record and flush to DB."""
    return await repo.create(file_id=file_id)


# ── Tests ──────────────────────────────────────────────────────


class TestDocumentRepository:
    async def test_create_document_record(self, db_session):
        """Creating a record sets status=processing and returns the ORM object."""
        repo = DocumentRepository(db_session)
        document = await _create_record(repo)

        assert document.uuid == "test-uuid-1"
        assert document.status == DocumentStatus.processing

    async def test_get_by_uuid_found(self, db_session):
        """get_by_uuid returns the record when it exists."""
        repo = DocumentRepository(db_session)
        await _create_record(repo)

        result = await repo.get_by_uuid("test-uuid-1")
        assert result is not None
        assert result.uuid == "test-uuid-1"

    async def test_get_by_uuid_not_found(self, db_session):
        """get_by_uuid returns None for a missing record."""
        repo = DocumentRepository(db_session)
        result = await repo.get_by_uuid("nonexistent")
        assert result is None

    async def test_get_by_uuid_or_raise(self, db_session):
        """get_by_uuid_or_raise raises DocumentNotFoundException if missing."""
        repo = DocumentRepository(db_session)
        with pytest.raises(DocumentNotFoundException):
            await repo.get_by_uuid_or_raise("nonexistent")

    async def test_delete_by_uuid(self, db_session):
        """delete_by_uuid removes the record and returns True."""
        repo = DocumentRepository(db_session)
        await _create_record(repo)

        deleted = await repo.delete_by_uuid("test-uuid-1")
        assert deleted is True

        # Confirm it's gone
        result = await repo.get_by_uuid("test-uuid-1")
        assert result is None

    async def test_update_manual_input(self, db_session):
        """update_manual_input merges new fields into manual_input JSON."""
        repo = DocumentRepository(db_session)
        document = await _create_record(repo)

        payload = {
            "department": {
                "old": "Finance",
                "new": "Accounting",
                "description": "correction",
            }
        }
        updated = await repo.update_manual_input(document, payload)

        assert updated.manual_input is not None
        assert "department" in updated.manual_input
        assert updated.manual_input["department"]["new"] == "Accounting"
