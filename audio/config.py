from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MinIO / S3
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    audio_bucket: str = "meeting-audio"

    # Server
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
