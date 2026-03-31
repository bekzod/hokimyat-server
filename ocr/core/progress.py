"""
Document processing progress tracking via Redis.

Stores lightweight progress info in Redis so the status endpoint
can return real-time progress without extra DB queries.
"""

import json
import logging

import redis

from core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = get_settings().redis_url
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


def _key(file_id: str) -> str:
    return f"doc_progress:{file_id}"


def set_progress(file_id: str, percent: int, stage: str) -> None:
    """Update processing progress for a document."""
    try:
        r = _get_redis()
        r.setex(_key(file_id), 600, json.dumps({"percent": percent, "stage": stage}))
    except Exception:
        logger.debug("Failed to set progress for %s", file_id, exc_info=True)


def get_progress(file_id: str) -> dict | None:
    """Read current progress. Returns {"percent": int, "stage": str} or None."""
    try:
        r = _get_redis()
        raw = r.get(_key(file_id))
        if raw:
            return json.loads(raw)
    except Exception:
        logger.debug("Failed to get progress for %s", file_id, exc_info=True)
    return None


def clear_progress(file_id: str) -> None:
    """Remove progress key after processing completes."""
    try:
        r = _get_redis()
        r.delete(_key(file_id))
    except Exception:
        pass
