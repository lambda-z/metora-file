from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from typing import BinaryIO

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._/-]+")


class StorageBackend(ABC):
    """
    Abstract object storage backend.

    Mirrors the shape of ``metora.providers.storage.StorageProviderProtocol``:
    a backend is responsible only for the file body. Metadata lives in MongoDB.
    """

    name: str = "base"

    def build_key(self, *, bucket: str, object_key: str | None, filename: str) -> str:
        """Compute a deterministic-ish storage key for a new object."""
        safe_name = _SAFE_SEGMENT.sub("-", filename or "file").strip("-/") or "file"
        if object_key:
            cleaned = _SAFE_SEGMENT.sub("-", object_key).strip("/")
            if cleaned:
                return f"{bucket}/{cleaned}"
        return f"{bucket}/{uuid.uuid4().hex}/{safe_name}"

    @abstractmethod
    def put_object(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> dict:
        """Store bytes under ``key``. Returns metadata such as ``size`` and ``etag``."""

    @abstractmethod
    def open_stream(self, *, key: str) -> BinaryIO:
        """Return a binary stream of the stored object (used by local serving)."""

    @abstractmethod
    def get_download_url(self, *, key: str, expires: int = 300, filename: str | None = None) -> str:
        """Return a time-limited URL that serves the object body."""

    @abstractmethod
    def delete(self, *, key: str) -> None:
        """Remove the stored object body. Should be idempotent."""
