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

    # Redis / Celery
    redis_url: str

    # AI / vLLM
    vllm_url: str = "http://vllm:8000"
    openai_api_base_url: str = ""
    openai_api_key: str = ""
    default_models: str = ""
    vllm_structured_output_enabled: bool = True

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
