"""
API v1 Router — combines all v1 endpoint routers.

Mounted at /api/ in main.py to preserve backward compatibility.
"""

from fastapi import APIRouter

from .endpoints import upload, status, health

api_router = APIRouter()

# /api/upload-pdf/ and /api/upload-document/
api_router.include_router(upload.router, tags=["upload"])

# /api/status/{file_id} and /api/manual-update/{file_id}
api_router.include_router(status.router, tags=["status"])

# /api/health and /api/ai-health
api_router.include_router(health.router, tags=["health"])
