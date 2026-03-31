"""
Analyze Endpoint — run AI analysis on raw text without file upload.

  POST /api/analyze-text/
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from library.ai import (
    check_for_repeated_request,
    extract_author_information,
    extract_issues,
    get_entity_type,
    select_department,
    summarize,
)
from pydantic import BaseModel
from utils.text import clean_extracted_content

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeTextRequest(BaseModel):
    text: str


@router.post("/analyze-text/", tags=["analyze"])
async def analyze_text(body: AnalyzeTextRequest):
    """Run AI analysis tasks on raw text input."""
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    cleaned = clean_extracted_content(text)
    author_input = cleaned[:6000] if len(cleaned) > 3200 else cleaned

    import asyncio

    (
        summary_result,
        author_info_result,
        issues_result,
        entity_result,
        repeated_result,
        department_result,
    ) = await asyncio.gather(
        summarize(cleaned),
        extract_author_information(author_input),
        extract_issues(cleaned),
        get_entity_type(cleaned[:3200]),
        check_for_repeated_request(cleaned),
        select_department(summary=cleaned),
        return_exceptions=True,
    )

    def safe(val):
        return None if isinstance(val, Exception) else val

    meta = {
        "summary": safe(summary_result),
        "author_info": safe(author_info_result),
        "issues": safe(issues_result),
        "entity": safe(entity_result),
        "is_repeated": (
            safe(repeated_result).get("is_repeated")
            if safe(repeated_result)
            else None
        ),
        "repeated_dates": (
            safe(repeated_result).get("dates") if safe(repeated_result) else None
        ),
        "department": safe(department_result),
    }

    return JSONResponse(content={"status": "completed", "meta": meta})
