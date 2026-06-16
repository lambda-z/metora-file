from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    backend = (settings.storage_backend or "local").lower()
    if backend == "minio":
        from app.storage.minio import MinioBackend

        return MinioBackend()
    return LocalBackend()
