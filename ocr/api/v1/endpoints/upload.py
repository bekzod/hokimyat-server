"""
Upload Endpoints — document upload API routes.

Preserves the same URL paths as master:
  POST /api/upload-pdf/
  POST /api/upload-document/
"""

import logging
import time

from api.deps import get_document_service
from core.exceptions import StorageException, ValidationException
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from services.document_service import DocumentService
from workers.tasks import process_document_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload-pdf/", status_code=202, tags=["upload"])
@router.post("/upload-document/", status_code=202, tags=["upload"])
async def upload_document(
    file: UploadFile,
    tasks: str = Form(
        None,
        description="Comma separated list of tasks to run (e.g. entity,summarization,department,repeated). "
        "If not provided, all tasks are run.",
    ),
    document_service: DocumentService = Depends(get_document_service),
):
    """Upload a document for async processing. Returns file_id for status tracking."""
    task_start_time = time.time()

    logger.debug(
        f"Raw filename value: {repr(file.filename)} (type: {type(file.filename)})"
    )

    try:
        document_record = await document_service.upload_document(file=file)
    except ValidationException as e:
        logger.debug(f"Upload rejected: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except StorageException as e:
        logger.error(f"Storage error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file to storage")

    # Queue the background processing task
    process_document_task.apply_async(
        args=[document_record.uuid, tasks, task_start_time]
    )

    return JSONResponse(
        status_code=202,
        content={
            "message": "File received, processing started",
            "file_id": document_record.uuid,
            "status": "processing",
        },
    )
