"""
Health Endpoints — service health check API routes.

Preserves the same URL paths as master:
  GET /api/health
  GET /api/ai-health
"""

import logging
import os

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check():
    """Check if the main service is operational."""
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "message": "Service is operational"},
    )


@router.get("/ai-health", tags=["health"])
async def ai_health_check():
    """Check if the vLLM AI backend is accessible."""
    settings = get_settings()
    vllm_url = settings.vllm_url

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{vllm_url}/v1/models")

            if response.status_code == 200:
                return JSONResponse(
                    status_code=200,
                    content={"is_healthy": True},
                )
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "is_healthy": False,
                        "error": response.text
                    },
                )

    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"is_healthy": False, "error": "Connection refused"},
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=503,
            content={"is_healthy": False, "error": "Request timed out"},
        )
    except Exception as e:
        logger.error(f"Error checking VLLM health: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"is_healthy": False, "error": str(e)},
        )
