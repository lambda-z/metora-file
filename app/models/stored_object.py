from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field

from app.models.enums import ObjectStatus, ObjectVisibility


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StoredObject(Document):
    bucket_name: str
    object_key: str
    storage_key: str

    # Bucket-relative folder path (normalised, e.g. "images/2024"); "" = root.
    folder: str = ""
    # Virtual folder marker (no bytes); created so an empty folder persists.
    is_placeholder: bool = False

    filename: str | None = None
    content_type: str | None = None
    size: int = 0
    etag: str | None = None

    visibility: ObjectVisibility = ObjectVisibility.PRIVATE
    status: ObjectStatus = ObjectStatus.ACTIVE

    source_system: str | None = None
    owner_type: str | None = None
    owner_id: str | None = None

    uploader_type: str | None = None
    uploader_id: str | None = None

    current_generation: int = 1
    metadata: dict = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    deleted_at: datetime | None = None

    class Settings:
        name = "stored_objects"
        indexes = [
            pymongo.IndexModel(
                [("bucket_name", pymongo.ASCENDING), ("object_key", pymongo.ASCENDING)],
            ),
            pymongo.IndexModel(
                [("bucket_name", pymongo.ASCENDING), ("folder", pymongo.ASCENDING)],
            ),
            "status",
            "source_system",
            "owner_type",
            "owner_id",
            [("created_at", pymongo.DESCENDING)],
        ]
