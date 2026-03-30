"""
Tests for PDFRepository — async CRUD against in-memory SQLite.

Each test gets a fresh database via the db_session fixture,
so tests are fully isolated from each other.
"""

import pytest
from core.exceptions import PDFNotFoundException
from models.pdf import PDFStatus
from repositories.pdf_repository import PDFRepository


# ── Helper ─────────────────────────────────────────────────────


async def _create_record(repo: PDFRepository, file_id: str = "test-uuid-1"):
    """Shortcut to create a PDF record and flush to DB."""
    return await repo.create(file_id=file_id, employee_id=1, doc_type="invoice")


# ── Tests ──────────────────────────────────────────────────────


class TestPDFRepository:
    async def test_create_pdf_record(self, db_session):
        """Creating a record sets status=processing and returns the ORM object."""
        repo = PDFRepository(db_session)
        pdf = await _create_record(repo)

        assert pdf.uuid == "test-uuid-1"
        assert pdf.status == PDFStatus.processing
        assert pdf.employee_id == 1
        assert pdf.doc_type == "invoice"

    async def test_get_by_uuid_found(self, db_session):
        """get_by_uuid returns the record when it exists."""
        repo = PDFRepository(db_session)
        await _create_record(repo)

        result = await repo.get_by_uuid("test-uuid-1")
        assert result is not None
        assert result.uuid == "test-uuid-1"

    async def test_get_by_uuid_not_found(self, db_session):
        """get_by_uuid returns None for a missing record."""
        repo = PDFRepository(db_session)
        result = await repo.get_by_uuid("nonexistent")
        assert result is None

    async def test_get_by_uuid_or_raise(self, db_session):
        """get_by_uuid_or_raise raises PDFNotFoundException if missing."""
        repo = PDFRepository(db_session)
        with pytest.raises(PDFNotFoundException):
            await repo.get_by_uuid_or_raise("nonexistent")

    async def test_delete_by_uuid(self, db_session):
        """delete_by_uuid removes the record and returns True."""
        repo = PDFRepository(db_session)
        await _create_record(repo)

        deleted = await repo.delete_by_uuid("test-uuid-1")
        assert deleted is True

        # Confirm it's gone
        result = await repo.get_by_uuid("test-uuid-1")
        assert result is None

    async def test_update_manual_input(self, db_session):
        """update_manual_input merges new fields into manual_input JSON."""
        repo = PDFRepository(db_session)
        pdf = await _create_record(repo)

        payload = {
            "department": {
                "old": "Finance",
                "new": "Accounting",
                "description": "correction",
            }
        }
        updated = await repo.update_manual_input(pdf, payload)

        assert updated.manual_input is not None
        assert "department" in updated.manual_input
        assert updated.manual_input["department"]["new"] == "Accounting"
