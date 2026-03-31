"""
Status Endpoints — document status and manual update API routes.

Preserves the same URL paths as master:
  GET  /api/status/{file_id}
  POST /api/manual-update/{file_id}
"""

import logging

from api.deps import get_document_service
from core.exceptions import DocumentNotFoundException, ValidationException
from core.progress import get_progress
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from models.pdf import DocumentStatus
from services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status/{file_id}", tags=["status"])
async def check_status(
    file_id: str,
    document_service: DocumentService = Depends(get_document_service),
):
    """Get document processing status and extracted metadata."""
    try:
        document_record = await document_service.get_status(file_id)
    except DocumentNotFoundException:
        raise HTTPException(
            status_code=404, detail="File not found or status not available"
        )

    response = {
        "file_id": document_record.uuid,
        "status": document_record.status.value,
        "created_at": (
            document_record.created_at.isoformat()
            if document_record.created_at
            else None
        ),
        "updated_at": (
            document_record.updated_at.isoformat()
            if document_record.updated_at
            else None
        ),
    }

    if document_record.status.value == "processing":
        progress = get_progress(document_record.uuid)
        if progress:
            response["progress"] = progress["percent"]
            response["progress_stage"] = progress["stage"]

    if document_record.processed_at:
        response["processed_at"] = document_record.processed_at.isoformat()

    if document_record.error_message:
        response["error_message"] = document_record.error_message

    if document_record.status == DocumentStatus.completed:
        response["content"] = document_record.content
        response["meta"] = document_record.meta
        response["total_page_count"] = document_record.total_page_count

    return response


@router.post("/manual-update/{file_id}", tags=["status"])
async def manual_update(
    file_id: str,
    payload: dict = Body(
        ...,
        example={
            "department": {
                "old": "Finance",
                "new": "Accounting",
                "description": "Department name correction",
            },
        },
    ),
    document_service: DocumentService = Depends(get_document_service),
):
    """Manually update or correct extracted metadata."""
    try:
        document_record = await document_service.update_manual_input(file_id, payload)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DocumentNotFoundException:
        raise HTTPException(status_code=404, detail="File not found")

    return JSONResponse(
        status_code=200,
        content={
            "file_id": document_record.uuid,
            "message": "Metadata updated successfully",
            "meta": document_record.meta,
        },
    )
