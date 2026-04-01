"""
Officials Endpoint — serve the list of district officials from YAML.

  GET /api/officials/
"""

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "toshkent-tumani-officials.yaml"


@router.get("/officials/")
async def list_officials():
    with open(DATA_PATH, encoding="utf-8") as f:
        officials = yaml.safe_load(f)
    return JSONResponse(content=officials)
