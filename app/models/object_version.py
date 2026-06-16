from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ObjectVersion(Document):
    object_id: PydanticObjectId
    generation: int
    storage_key: str

    size: int = 0
    content_type: str | None = None
    etag: str | None = None

    uploader_type: str | None = None
    uploader_id: str | None = None

    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "object_versions"
        indexes = [
            pymongo.IndexModel(
                [("object_id", pymongo.ASCENDING), ("generation", pymongo.DESCENDING)],
                unique=True,
            ),
        ]
