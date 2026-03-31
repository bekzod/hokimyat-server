"""
Extraction Service — PDF content extraction and AI task orchestration.

CRITICAL: This uses master's business logic:
  - force_ocr: True (scanned PDFs need OCR)
  - MAX_PAGE_RANGE from settings (default 50, not 6)
  - author_input = content[:6000] when full content is long enough
  - Semaphore-controlled parallel AI tasks
"""

import asyncio
import logging
import math
import time
from typing import Any, Callable, List, Optional

import aiohttp
from core.config import get_settings

# Import AI functions from library/ai.py — these stay in place
# because they contain complex business logic (fuzzy matching, prompts, etc.)
from library.ai import (
    check_for_repeated_request,
    extract_author_information,
    extract_issues,
    get_entity_type,
    select_department,
    select_document_type,
    summarize,
)

logger = logging.getLogger(__name__)

# Default set of AI extraction tasks
DEFAULT_TASKS = [
    "author_info",
    "summary",
    "repeated_info",
    "entity_type",
    "issues",
    "department",
    "document_type",
]

# Maximum word limit for content processing
MAX_WORDS_LIMIT = 20500

# Client timeout for HTTP requests (in seconds)
_CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=360)


# Map MIME types to Docling from_formats values
_MIME_TO_FORMAT = {
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/tiff": "image",
    "image/bmp": "image",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def content_type_to_format(content_type: str | None) -> str:
    """Convert a MIME content type to a Docling from_formats value."""
    return _MIME_TO_FORMAT.get(content_type or "", "pdf")


def _build_extraction_options(settings, from_format: str = "pdf") -> dict:
    """Build extraction options using current settings.

    Uses force_ocr=True and MAX_PAGE_RANGE from config (default 50)
    so scanned PDFs are properly OCR'd and all pages are processed.
    """
    opts = {
        "image_export_mode": "placeholder",
        "force_ocr": True,
        "from_formats": [from_format],
        "to_formats": ["md"],
        "ocr": True,
        "ocr_engine": "tesseract",
        "ocr_lang": ["uzb_cyrl", "uzb"],
        "table_mode": "accurate",
        "pipeline": "standard",
        "abort_on_error": True,
        "do_table_structure": True,
        "include_images": False,
        "images_scale": 1,
        "md_page_break_placeholder": "<<Page break>>",
        "do_code_enrichment": False,
        "do_formula_enrichment": False,
        "do_picture_classification": False,
        "do_picture_description": False,
        "picture_description_area_threshold": 0.05,
    }
    # page_range only applies to multi-page formats (PDF)
    if from_format == "pdf":
        opts["page_range"] = [1, settings.max_page_range]
    return opts


class ExtractionService:
    """
    Service for PDF extraction and AI processing.

    Handles content extraction from documents via Docling and
    orchestration of parallel AI extraction tasks.
    """

    def __init__(self):
        settings = get_settings()
        self.docling_host = settings.docling_host
        self._settings = settings
        self._max_page_range = settings.max_page_range

    async def extract_pdf_content(
        self,
        presigned_url: str,
        page_range: Optional[List[int]] = None,
        do_table_structure: bool = True,
        from_format: str = "pdf",
        session: Optional[aiohttp.ClientSession] = None,
    ) -> str:
        """Extract markdown content from a document via Docling."""
        url = f"{self.docling_host}/v1/convert/source"

        extraction_options = _build_extraction_options(self._settings, from_format)
        if page_range and from_format == "pdf":
            extraction_options["page_range"] = page_range
            logger.info(f"Using custom page_range: {page_range}")
        if do_table_structure is not None:
            extraction_options["do_table_structure"] = do_table_structure

        payload = {
            "sources": [{"url": presigned_url, "kind": "http"}],
            "options": extraction_options,
        }

        session_provided = session is not None
        if not session_provided:
            session = aiohttp.ClientSession()

        try:
            async with session.post(
                url,
                json=payload,
                timeout=_CLIENT_TIMEOUT,
            ) as response:
                if response.status == 404:
                    logger.warning("API returned 404, returning empty string")
                    return ""
                elif response.status != 200:
                    text = await response.text()
                    logger.error(
                        f"API request failed with status code {response.status}: {text}"
                    )
                    raise Exception(
                        f"PDF extraction API returned error: {response.status}"
                    )
                result_json = await response.json()
                return result_json.get("document", {}).get("md_content", "")
        finally:
            if not session_provided:
                await session.close()

    async def run_ai_tasks(
        self,
        content: str,
        first_page_content: str,
        tasks_to_run: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        """
        Run AI extraction tasks in parallel with controlled concurrency.

        Uses master's business logic:
        - author_input = content[:6000] when full content > 3200 chars
          (so complainant details beyond the cover page are visible to the LLM)
        - Semaphore concurrency based on task count
        """
        if not tasks_to_run:
            tasks_to_run = DEFAULT_TASKS

        tasks_to_run = [t.strip() for t in tasks_to_run if t.strip()]
        results: dict[str, Any] = {}
        errors: list[dict[str, str]] = []

        async def safe_task(task_name: str, task_fn: Callable, *args):
            """Wrap an LLM/AI call so one failure doesn't kill the whole job."""
            start = time.time()
            try:
                logger.info("Started %s", task_name)
                if asyncio.iscoroutinefunction(task_fn):
                    return await task_fn(*args)
                return await asyncio.to_thread(task_fn, *args)
            except Exception as exc:
                msg = str(exc)
                logger.error("Error in %s: %s", task_name, msg, exc_info=True)
                errors.append({"name": task_name, "error": msg})
                return None
            finally:
                logger.info("Task %s finished in %.2fs", task_name, time.time() - start)

        # Build task list based on requested tasks
        tasks: list[tuple[str, Callable, Any]] = []

        if "summary" in tasks_to_run:
            tasks.append(("summary", summarize, content))

        if "author_info" in tasks_to_run:
            # CRITICAL: Use first ~6000 chars of full content so complainant
            # details beyond a cover-letter first page are visible to the LLM.
            author_input = content[:6000] if len(content) > 3200 else first_page_content
            tasks.append(("author_info", extract_author_information, author_input))
        if "document_type" in tasks_to_run:
            tasks.append(("document_type", select_document_type, first_page_content))

        if "entity_type" in tasks_to_run:
            tasks.append(("entity_type", get_entity_type, first_page_content))
        if "repeated_info" in tasks_to_run:
            tasks.append(("repeated", check_for_repeated_request, content))
        if "issues" in tasks_to_run:
            tasks.append(("issues", extract_issues, content))
        if "department" in tasks_to_run:
            tasks.append(("department", select_department, content))

        # Calculate concurrency — same logic as master's app/tasks.py
        num_tasks = len(tasks)
        if num_tasks <= 5:
            concurrency = max(1, num_tasks)
        else:
            concurrency = math.ceil(num_tasks / 2)

        semaphore = asyncio.Semaphore(concurrency)

        async def sem_task(name, fn, *args):
            async with semaphore:
                return await safe_task(name, fn, *args)

        # Execute all tasks in parallel
        task_results = await asyncio.gather(
            *(sem_task(name, fn, *args) for name, fn, *args in tasks)
        )

        # Map results back to task names
        for task, result in zip(tasks, task_results):
            name = task[0]
            results[name] = result

        # Build final aggregated response — same structure as master
        final = {
            "summary": results.get("summary"),
            "is_repeated": (
                results.get("repeated", {}).get("is_repeated")
                if results.get("repeated")
                else None
            ),
            "repeated_dates": (
                results.get("repeated", {}).get("dates")
                if results.get("repeated")
                else None
            ),
            "entity": results.get("entity_type"),
            "document_type": results.get("document_type"),
            "issues": results.get("issues"),
            "department": results.get("department"),
            "errors": errors or None,
        }

        # Store author_info as a nested key (same as master)
        if results.get("author_info"):
            final["author_info"] = results["author_info"]

        return final


# Singleton instance
_extraction_service: Optional[ExtractionService] = None


def get_extraction_service() -> ExtractionService:
    """Get or create extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ExtractionService()
    return _extraction_service
