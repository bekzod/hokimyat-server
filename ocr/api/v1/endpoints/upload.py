"""
Upload Endpoints — document upload API routes.

Preserves the same URL paths as master:
  POST /api/upload-pdf/
  POST /api/upload-document/
"""

import logging
import time

from fastapi import APIRouter, UploadFile, HTTPException, Depends, Form
from fastapi.responses import JSONResponse

from api.deps import get_pdf_service
from core.exceptions import ValidationException, StorageException
from services.pdf_service import PDFService
from workers.tasks import process_pdf_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload-pdf/", status_code=202, tags=["upload"])
@router.post("/upload-document/", status_code=202, tags=["upload"])
async def upload_document(
    file: UploadFile,
    tasks: str = Form(
        None,
        description="Comma separated list of tasks to run (e.g. entity,summarization,department,repeated,category). "
        "If not provided, all tasks are run.",
    ),
    employee_id: int = Form(
        None, description="Integer ID of the employee associated with this PDF"
    ),
    employment_id: int = Form(
        None, description="Integer ID of the employment record associated with this PDF"
    ),
    doc_type: str = Form(
        None, description="Type of document being uploaded (e.g. invoice, contract, receipt)"
    ),
    pdf_service: PDFService = Depends(get_pdf_service),
):
    """Upload a document for async processing. Returns file_id for status tracking."""
    task_start_time = time.time()

    logger.debug(f"Raw filename value: {repr(file.filename)} (type: {type(file.filename)})")

    try:
        pdf_record = await pdf_service.upload_document(
            file=file,
            employee_id=employee_id,
            employment_id=employment_id,
            doc_type=doc_type,
        )
    except ValidationException as e:
        logger.debug(f"Upload rejected: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except StorageException as e:
        logger.error(f"Storage error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file to storage")

    # Queue the background processing task
    process_pdf_task.apply_async(
        args=[pdf_record.uuid, tasks, task_start_time]
    )

    return JSONResponse(
        status_code=202,
        content={
            "message": "File received, processing started",
            "file_id": pdf_record.uuid,
            "status": "processing",
            "employee_id": employee_id,
            "employment_id": employment_id,
            "doc_type": doc_type,
        },
    )
