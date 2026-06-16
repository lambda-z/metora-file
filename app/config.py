from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "metora_file"

    # Storage backend selection: "local" | "minio"
    storage_backend: str = "local"
    local_storage_dir: str = "./.data/objects"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_default_bucket: str = "metora-file"

    # Admin UI
    admin_ui_enabled: bool = True
    admin_ui_basic_auth_username: str = "admin"
    admin_ui_basic_auth_password: str = "admin123"

    # Service
    base_url: str = "http://localhost:8000"
    signing_secret: str = "change-me-in-production"
    api_token_env: str = "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
