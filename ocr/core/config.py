"""
Centralized configuration management using Pydantic Settings.

All environment variables are loaded here and can be accessed via get_settings().
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    ocr_server_database_url: str

    # MinIO / S3 Storage
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_uploads_bucket: str = "ocr-server-uploads"

    storage_provider: str = "minio"
    r2_endpoint: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""

    # Redis / Celery
    redis_url: str

    # AI / vLLM

    openai_api_base_url: str = ""
    openai_api_key: str = ""

    # Docling
    docling_host: str = "http://docling:5001"

    # PDF extraction limits
    max_page_range: int = 50

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()

