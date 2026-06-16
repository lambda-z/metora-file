from __future__ import annotations

import io
from datetime import timedelta
from typing import BinaryIO

from app.config import settings
from app.storage.base import StorageBackend


class MinioBackend(StorageBackend):
    """MinIO / S3-compatible object storage backend.

    All objects are stored inside a single MinIO bucket (``minio_default_bucket``);
    the logical bucket name is encoded in the storage key prefix.
    """

    name = "minio"

    def __init__(self) -> None:
        # Imported lazily so the local backend works without the dependency installed.
        from minio import Minio

        self._bucket = settings.minio_default_bucket
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def put_object(self, *, key: str, data: bytes, content_type: str | None = None) -> dict:
        result = self._client.put_object(
            self._bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type or "application/octet-stream",
        )
        return {"size": len(data), "etag": getattr(result, "etag", None)}

    def open_stream(self, *, key: str) -> BinaryIO:
        response = self._client.get_object(self._bucket, key)
        return io.BytesIO(response.read())

    def get_download_url(
        self, *, key: str, expires: int = 300, filename: str | None = None
    ) -> str:
        extra = None
        if filename:
            extra = {"response-content-disposition": f'attachment; filename="{filename}"'}
        return self._client.presigned_get_object(
            self._bucket,
            key,
            expires=timedelta(seconds=expires),
            response_headers=extra,
        )

    def delete(self, *, key: str) -> None:
        self._client.remove_object(self._bucket, key)
