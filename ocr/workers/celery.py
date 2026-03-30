"""
Celery Configuration — background task queue setup.

Uses Redis as broker with SSL support.
"""

from celery import Celery

from core.config import get_settings

# Build Redis URL with SSL options from centralized settings
redis_url = get_settings().redis_url
redis_url = f"{redis_url}?ssl_cert_reqs=CERT_NONE"

if not redis_url.startswith("rediss://"):
    redis_url = redis_url.replace("redis://", "rediss://")

celery_app = Celery("worker", broker=redis_url)

celery_app.conf.update(
    task_always_eager=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
