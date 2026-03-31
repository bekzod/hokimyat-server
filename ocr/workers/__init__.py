# Workers module — Celery task definitions
from .celery import celery_app
from .tasks import process_document_task

__all__ = ["celery_app", "process_document_task"]
