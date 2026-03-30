"""
Tests for API endpoint contracts — HTTP status codes and response shapes.

Uses httpx AsyncClient against a test FastAPI app with:
- In-memory SQLite DB (via conftest fixtures)
- Mock MinIO storage (no real uploads)
- Mock Celery task (no real queue dispatch)
"""

import uuid

import pytest


# ── Health ─────────────────────────────────────────────────────


class TestHealthEndpoint:
    async def test_health_returns_200(self, client):
        """GET /api/health should always return 200 with status=healthy."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


# ── Upload ─────────────────────────────────────────────────────


class TestUploadEndpoint:
    async def test_upload_pdf_returns_202(self, client):
        """POST /api/upload-pdf/ with a valid PDF returns 202 + file_id."""
        response = await client.post(
            "/api/upload-pdf/",
            files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        assert response.status_code == 202
        data = response.json()
        assert "file_id" in data
        assert data["status"] == "processing"
        # Verify Celery task was dispatched
        client.mock_task.apply_async.assert_called_once()

    async def test_upload_bad_content_type_returns_400(self, client):
        """POST /api/upload-pdf/ with unsupported MIME type returns 400."""
        response = await client.post(
            "/api/upload-pdf/",
            files={"file": ("malware.exe", b"MZ", "application/x-msdownload")},
        )
        assert response.status_code == 400


# ── Status ─────────────────────────────────────────────────────


class TestStatusEndpoint:
    async def test_status_found_returns_200(self, client):
        """GET /api/status/{id} returns 200 with processing status after upload."""
        # Create a record first via the upload endpoint
        upload = await client.post(
            "/api/upload-pdf/",
            files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        )
        file_id = upload.json()["file_id"]

        response = await client.get(f"/api/status/{file_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == file_id
        assert data["status"] == "processing"

    async def test_status_not_found_returns_404(self, client):
        """GET /api/status/{id} returns 404 for unknown file_id."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/status/{fake_id}")
        assert response.status_code == 404


# ── Manual Update ──────────────────────────────────────────────


class TestManualUpdateEndpoint:
    async def test_manual_update_returns_200(self, client):
        """POST /api/manual-update/{id} with valid payload returns 200."""
        # Create a record first
        upload = await client.post(
            "/api/upload-pdf/",
            files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        )
        file_id = upload.json()["file_id"]

        response = await client.post(
            f"/api/manual-update/{file_id}",
            json={
                "department": {
                    "old": "Finance",
                    "new": "Accounting",
                    "description": "correction",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == file_id
        assert data["message"] == "Metadata updated successfully"

    async def test_manual_update_not_found_returns_404(self, client):
        """POST /api/manual-update/{id} returns 404 for unknown file_id."""
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/manual-update/{fake_id}",
            json={
                "department": {
                    "old": "A",
                    "new": "B",
                    "description": "fix",
                }
            },
        )
        assert response.status_code == 404

    async def test_manual_update_bad_payload_returns_400(self, client):
        """POST /api/manual-update/{id} with malformed payload returns 400."""
        # Create a record first
        upload = await client.post(
            "/api/upload-pdf/",
            files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        )
        file_id = upload.json()["file_id"]

        response = await client.post(
            f"/api/manual-update/{file_id}",
            json={"department": {"wrong_key": "value"}},
        )
        assert response.status_code == 400
