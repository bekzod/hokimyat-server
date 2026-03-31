"""
File Endpoint — serve original uploaded files for preview.

  HEAD /api/file/{file_id}  (content-type detection)
  GET  /api/file/{file_id}  (full file download)
"""

import logging

from api.deps import get_document_service
from core.exceptions import DocumentNotFoundException
from core.storage import get_storage
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head("/file/{file_id}", tags=["file"])
async def head_file(
    file_id: str,
    document_service: DocumentService = Depends(get_document_service),
):
    """Return file metadata without downloading the file content."""
    try:
        await document_service.get_status(file_id)
    except DocumentNotFoundException:
        raise HTTPException(status_code=404, detail="File not found")

    storage = get_storage()

    file_meta = await storage.get_file_metadata(file_id)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found in storage")

    content_type = file_meta.get("content_type", "application/octet-stream")
    content_length = file_meta.get("content_length", 0)

    return Response(
        content=b"",
        media_type=content_type,
        headers={
            "Content-Length": str(content_length),
            "Content-Disposition": "inline",
        },
    )


@router.get("/file/{file_id}", tags=["file"])
async def get_file(
    file_id: str,
    document_service: DocumentService = Depends(get_document_service),
):
    """Serve the original uploaded file for preview."""
    try:
        await document_service.get_status(file_id)
    except DocumentNotFoundException:
        raise HTTPException(status_code=404, detail="File not found")

    storage = get_storage()

    file_meta = await storage.get_file_metadata(file_id)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found in storage")

    content_type = file_meta.get("content_type", "application/octet-stream")

    file_content = await storage.download_file(file_id)

    return Response(
        content=file_content,
        media_type=content_type,
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "private, max-age=3600",
        },
    )
