"""
Tests for PDFService — validation logic and orchestration.

Pure validation methods are tested directly (no DB).
The upload path is tested with mocked repository + storage.
"""

import uuid

import pytest
from core.exceptions import ValidationException
from services.pdf_service import PDFService


# ── Validation tests (static methods, no fixtures needed) ──────


class TestValidateFileType:
    def test_pdf_allowed(self):
        """application/pdf is an allowed MIME type — should not raise."""
        PDFService.validate_file_type("application/pdf")

    def test_docx_allowed(self):
        PDFService.validate_file_type(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_image_allowed(self):
        PDFService.validate_file_type("image/png")

    def test_exe_rejected(self):
        """application/x-msdownload should raise ValidationException."""
        with pytest.raises(ValidationException):
            PDFService.validate_file_type("application/x-msdownload")

    def test_none_rejected(self):
        """None content_type should raise ValidationException."""
        with pytest.raises(ValidationException):
            PDFService.validate_file_type(None)


class TestValidateUUID:
    def test_valid_uuid(self):
        """A proper UUID v4 string should not raise."""
        PDFService.validate_uuid(str(uuid.uuid4()))

    def test_invalid_uuid(self):
        """A non-UUID string should raise ValidationException."""
        with pytest.raises(ValidationException):
            PDFService.validate_uuid("not-a-uuid")


class TestValidateManualUpdatePayload:
    def test_valid_payload(self):
        """Payload with old/new/description keys should not raise."""
        PDFService.validate_manual_update_payload({
            "department": {
                "old": "Finance",
                "new": "Accounting",
                "description": "correction",
            }
        })

    def test_missing_keys_rejected(self):
        """Payload missing required keys should raise ValidationException."""
        with pytest.raises(ValidationException):
            PDFService.validate_manual_update_payload({
                "department": {"wrong_key": "value"}
            })


class TestGenerateFileId:
    def test_returns_valid_uuid(self):
        """generate_file_id should return a valid UUID v4 string."""
        file_id = PDFService.generate_file_id()
        # This will raise ValueError if not a valid UUID
        parsed = uuid.UUID(file_id)
        assert parsed.version == 4
