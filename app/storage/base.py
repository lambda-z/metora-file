from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from typing import BinaryIO

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._/-]+")


def normalize_folder(folder: str | None) -> str:
    """Normalise a bucket-relative folder path into a safe ``a/b/c`` prefix.

    - sanitises each path segment (same charset as storage keys),
    - drops empty / ``.`` / ``..`` segments (no traversal, no leading/trailing
      slashes),
    - returns ``""`` for an empty / root folder.
    """
    if not folder:
        return ""
    segments: list[str] = []
    for raw in folder.split("/"):
        seg = _SAFE_SEGMENT.sub("-", raw).strip("-").strip()
        if not seg or seg in (".", ".."):
            continue
        segments.append(seg)
    return "/".join(segments)


class StorageBackend(ABC):
    """
    Abstract object storage backend.

    Mirrors the shape of ``metora.providers.storage.StorageProviderProtocol``:
    a backend is responsible only for the file body. Metadata lives in MongoDB.
    """

    name: str = "base"

    def build_key(
        self,
        *,
        bucket: str,
        object_key: str | None,
        filename: str,
        folder: str | None = None,
    ) -> str:
        """Compute a deterministic-ish storage key for a new object.

        ``folder`` is an optional bucket-relative folder path that is prefixed
        onto the key, so the resulting storage path — and therefore the signed
        download URL — reflects the folder the object lives in.
        """
        safe_name = _SAFE_SEGMENT.sub("-", filename or "file").strip("-/") or "file"
        prefix = bucket
        folder = normalize_folder(folder)
        if folder:
            prefix = f"{bucket}/{folder}"
        if object_key:
            cleaned = _SAFE_SEGMENT.sub("-", object_key).strip("/")
            if cleaned:
                return f"{prefix}/{cleaned}"
        return f"{prefix}/{uuid.uuid4().hex}/{safe_name}"

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
    def presigned_put_url(
        self, *, key: str, expires: int = 300, content_type: str | None = None
    ) -> dict:
        """Return upload instructions for a direct client-side PUT.

        Returns a dict shaped like ``{"url": str, "method": "PUT", "headers": dict}``.
        The caller uploads the bytes straight to storage (MinIO presigned PUT, or a
        signed local endpoint) without proxying through this service.
        """

    @abstractmethod
    def stat_object(self, *, key: str) -> dict:
        """Return ``{"size": int, "etag": str | None}`` for a stored object.

        Used after a direct upload to backfill size/etag onto the metadata record.
        Raises ``FileNotFoundError`` if the object body is missing.
        """

    @abstractmethod
    def delete(self, *, key: str) -> None:
        """Remove the stored object body. Should be idempotent."""
