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

    # CORS: comma-separated origins allowed to call the API / direct-upload
    # endpoints from a browser. Defaults to "*" (any origin) so browser direct
    # uploads (PUT /files/{key}) work from any frontend host. Set to an explicit
    # comma-separated list in production.
    cors_allow_origins: str = "*"

    @property
    def cors_allow_origin_list(self) -> list[str]:
        raw = (self.cors_allow_origins or "").strip()
        if raw in ("", "*"):
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
