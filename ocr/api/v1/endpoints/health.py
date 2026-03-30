"""
Health Endpoints — service health check API routes.

  GET /api/health
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check():
    """Check if the main service is operational."""
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "message": "Service is operational"},
    )
