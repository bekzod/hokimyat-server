"""
Status Endpoints — document status and manual update API routes.

Preserves the same URL paths as master:
  GET  /api/status/{file_id}
  POST /api/manual-update/{file_id}
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse

from api.deps import get_pdf_service
from core.exceptions import PDFNotFoundException, ValidationException
from models.pdf import PDFStatus
from services.pdf_service import PDFService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status/{file_id}", tags=["status"])
async def check_status(
    file_id: str,
    pdf_service: PDFService = Depends(get_pdf_service),
):
    """Get document processing status and extracted metadata."""
    try:
        pdf_record = await pdf_service.get_status(file_id)
    except PDFNotFoundException:
        raise HTTPException(
            status_code=404, detail="File not found or status not available"
        )

    response = {
        "file_id": pdf_record.uuid,
        "status": pdf_record.status.value,
        "employee_id": pdf_record.employee_id,
        "employment_id": pdf_record.employment_id,
        "doc_type": pdf_record.doc_type,
        "created_at": (
            pdf_record.created_at.isoformat() if pdf_record.created_at else None
        ),
        "updated_at": (
            pdf_record.updated_at.isoformat() if pdf_record.updated_at else None
        ),
    }

    if pdf_record.processed_at:
        response["processed_at"] = pdf_record.processed_at.isoformat()

    if pdf_record.error_message:
        response["error_message"] = pdf_record.error_message

    if pdf_record.status == PDFStatus.completed:
        response["content"] = pdf_record.content
        response["meta"] = pdf_record.meta
        response["total_page_count"] = pdf_record.total_page_count

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
                "description": "Department name correction"
            },
            "category": {
                "old": "Invoice",
                "new": "Receipt",
                "description": "Document category update"
            }
        },
    ),
    pdf_service: PDFService = Depends(get_pdf_service),
):
    """Manually update or correct extracted metadata."""
    try:
        pdf_record = await pdf_service.update_manual_input(file_id, payload)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PDFNotFoundException:
        raise HTTPException(status_code=404, detail="File not found")

    return JSONResponse(
        status_code=200,
        content={
            "file_id": pdf_record.uuid,
            "message": "Metadata updated successfully",
            "meta": pdf_record.meta,
        },
    )
