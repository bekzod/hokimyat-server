"""
Celery Tasks — background PDF processing.

Uses the service and repository layers but preserves master's exact
processing logic: force_ocr, MAX_PAGE_RANGE, author content[:6000], etc.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone

import aiohttp

from .celery import celery_app
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.storage import get_storage
from models.pdf import PDFStatus
from repositories.pdf_repository import PDFRepository
from services.extraction_service import get_extraction_service
from utils.text import clean_extracted_content

logger = logging.getLogger(__name__)

# Maximum word limit for content processing (same as master)
MAX_WORDS_LIMIT = 20500


@celery_app.task(bind=True, soft_time_limit=400, time_limit=610)
def process_pdf_task(
    self,
    file_id: str,
    tasks_to_run=None,
    task_start_time=None,
):
    """Celery task entry point for PDF processing."""
    return asyncio.run(
        _process_pdf_task_async(file_id, tasks_to_run, task_start_time)
    )


async def _process_pdf_task_async(
    file_id: str,
    tasks_to_run=None,
    task_start_time=None,
):
    """
    Async implementation of PDF processing.

    Orchestrates:
    1. PDF content extraction via Docling (first page + rest in parallel)
    2. AI task execution via ExtractionService
    3. Result storage via PDFRepository
    """
    process_start_time = time.time()
    if task_start_time is None:
        task_start_time = process_start_time

    settings = get_settings()
    max_page_range = settings.max_page_range

    async with AsyncSessionLocal() as db:
        repository = PDFRepository(db)
        storage = get_storage()
        extraction_service = get_extraction_service()

        pdf_record = None
        try:
            extract_start_time = time.time()

            # Fetch PDF record and generate presigned URL in parallel
            db_task = repository.get_by_uuid(file_id)
            presigned_url = await storage.generate_presigned_url(
                file_id, expiration=1800
            )

            # Extract content from first page and rest in parallel
            async with aiohttp.ClientSession() as session:
                first_page_task = extraction_service.extract_pdf_content(
                    presigned_url=presigned_url,
                    page_range=[1, 1],
                    do_table_structure=False,
                    session=session,
                )
                rest_pages_task = extraction_service.extract_pdf_content(
                    presigned_url=presigned_url,
                    page_range=[2, max_page_range],
                    do_table_structure=True,
                    session=session,
                )

                pdf_record, first_page_content, rest_pages_content = (
                    await asyncio.gather(db_task, first_page_task, rest_pages_task)
                )

            logger.info(
                f"First page content length: {len(first_page_content)} characters"
            )

            extract_time = time.time() - extract_start_time
            logger.info(f"PDF extraction completed in {extract_time:.2f} seconds")

            if not pdf_record:
                logger.error(f"No Document record found for id: {file_id}")
                return

            if not first_page_content:
                logger.error("Missing md_content for Document with id: %s", file_id)
                pdf_record.status = PDFStatus.failed
                pdf_record.error_message = "Missing md_content"
                pdf_record.processed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # Combine content and calculate page count
            content = first_page_content + "<<Page break>>" + rest_pages_content
            page_count = content.count("<<Page break>>")
            content = re.sub(r"<!-- image -->|<<Page break>>", "", content)
            pdf_record.content = content
            pdf_record.total_page_count = page_count + 1

            # Clean and truncate content for AI processing
            first_page_content = clean_extracted_content(first_page_content)[:3200]
            content = clean_extracted_content(content)

            words = content.split()
            if len(words) > MAX_WORDS_LIMIT:
                content = " ".join(words[:MAX_WORDS_LIMIT])

            # Parse tasks to run
            if tasks_to_run:
                tasks_to_run = [
                    task.strip() for task in tasks_to_run.split(",") if task.strip()
                ]

            # Run AI extraction tasks via the service
            meta = await extraction_service.run_ai_tasks(
                content=content,
                first_page_content=first_page_content,
                tasks_to_run=tasks_to_run,
            )

            # Add processing times to metadata
            total_process_time = time.time() - task_start_time
            ai_process_time = time.time() - process_start_time - extract_time

            meta["processing_times"] = {
                "total_time": round(total_process_time, 2),
                "extraction_time": round(extract_time, 2),
                "ai_processing_time": round(ai_process_time, 2),
            }

            pdf_record.meta = meta
            pdf_record.status = PDFStatus.completed
            pdf_record.processed_at = datetime.now(timezone.utc)
            await db.commit()

            total_time = time.time() - task_start_time
            logger.info(
                f"Finished processing PDF with id: {file_id} in {total_time:.2f} seconds"
            )
        except BaseException as e:
            logger.error(f"Error processing PDF with id: {file_id}", exc_info=True)
            if pdf_record:
                pdf_record.status = PDFStatus.failed
                pdf_record.error_message = str(e)
                pdf_record.processed_at = datetime.now(timezone.utc)
                await db.commit()
            raise
