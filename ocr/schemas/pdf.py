"""
Pydantic schemas for API request/response validation.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class PDFUploadResponse(BaseModel):
    message: str
    file_id: str
    status: str
    employee_id: Optional[int] = None
    employment_id: Optional[int] = None
    doc_type: Optional[str] = None


class PDFStatusResponse(BaseModel):
    file_id: str
    status: str
    employee_id: Optional[int] = None
    employment_id: Optional[int] = None
    doc_type: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    processed_at: Optional[str] = None
    error_message: Optional[str] = None
    content: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    total_page_count: Optional[int] = None


class ManualUpdateResponse(BaseModel):
    file_id: str
    message: str
    meta: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    message: str


class AIHealthResponse(BaseModel):
    is_healthy: bool
    error: Optional[str] = None
