"""
OCR Server — FastAPI Application

App factory pattern with router configuration.
All endpoint logic lives in api/v1/endpoints/; this file only wires things together.
"""

import logging
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from api.v1.router import api_router

# Configure logging from settings
settings = get_settings()
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(level=log_level)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="OCR Server",
        description="Document processing and AI extraction service",
        version="1.0.0",
    )

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    application.mount("/front", StaticFiles(directory="front", html=True), name="front")

    # Mount API router at /api/ to preserve existing client URLs
    # (e.g. /api/upload-pdf/, /api/status/{id}, /api/health)
    application.include_router(api_router, prefix="/api")

    return application


# Create the application instance (used by uvicorn)
app = create_app()
