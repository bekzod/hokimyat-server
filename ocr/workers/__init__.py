# Workers module — Celery task definitions
from .celery import celery_app
from .tasks import process_pdf_task

__all__ = ["celery_app", "process_pdf_task"]
