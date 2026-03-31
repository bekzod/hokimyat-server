"""
Documents Endpoints — list documents.
"""

from api.deps import get_document_service
from fastapi import APIRouter, Depends, Query
from services.document_service import DocumentService

router = APIRouter()


@router.get("/documents/", tags=["documents"])
async def list_documents(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    document_service: DocumentService = Depends(get_document_service),
):
    """List recent documents with basic info."""
    documents = await document_service.list_recent(limit=limit, offset=offset)
    return [
        {
            "file_id": doc.uuid,
            "status": doc.status.value,
            "total_page_count": doc.total_page_count,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "has_content": bool(doc.content),
        }
        for doc in documents
    ]
