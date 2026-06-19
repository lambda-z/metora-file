from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote, urlencode

from app.config import settings
from app.storage.base import StorageBackend
from app.storage.signing import make_signed_query


class LocalBackend(StorageBackend):
    """Local-disk storage backend used as a dev fallback (no MinIO needed).

    Download URLs point back at this service's signed ``/files/{key}`` endpoint.
    """

    name = "local"

    def __init__(self, root: str | None = None, base_url: str | None = None) -> None:
        self._root = Path(root or settings.local_storage_dir).resolve()
        self._base_url = (base_url or settings.base_url).rstrip("/")
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        # Prevent path traversal: resolve and ensure it stays under root.
        target = (self._root / key).resolve()
        if self._root not in target.parents and target != self._root:
            raise ValueError("Invalid storage key")
        return target

    def put_object(self, *, key: str, data: bytes, content_type: str | None = None) -> dict:
        target = self._path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {
            "size": len(data),
            "etag": hashlib.md5(data).hexdigest(),  # noqa: S324 - etag only, not security
        }

    def open_stream(self, *, key: str) -> BinaryIO:
        return self._path_for(key).open("rb")

    def get_download_url(
        self, *, key: str, expires: int = 300, filename: str | None = None
    ) -> str:
        expires_at, signature = make_signed_query(key, expires)
        params = {"expires": expires_at, "sig": signature}
        if filename:
            params["filename"] = filename
        return f"{self._base_url}/files/{quote(key)}?{urlencode(params)}"

    def presigned_put_url(
        self, *, key: str, expires: int = 300, content_type: str | None = None
    ) -> dict:
        expires_at, signature = make_signed_query(key, expires, action="put")
        params = {"expires": expires_at, "sig": signature}
        url = f"{self._base_url}/files/{quote(key)}?{urlencode(params)}"
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        return {"url": url, "method": "PUT", "headers": headers}

    def stat_object(self, *, key: str) -> dict:
        target = self._path_for(key)
        if not target.exists():
            raise FileNotFoundError(key)
        data = target.read_bytes()
        return {
            "size": target.stat().st_size,
            "etag": hashlib.md5(data).hexdigest(),  # noqa: S324 - etag only, not security
        }

    def delete(self, *, key: str) -> None:
        try:
            self._path_for(key).unlink()
        except FileNotFoundError:
            pass
