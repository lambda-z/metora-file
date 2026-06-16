from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field

from app.models.enums import BucketStatus, BucketVisibility


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Bucket(Document):
    name: str
    display_name: str | None = None
    visibility: BucketVisibility = BucketVisibility.PRIVATE
    storage_backend: str = "minio"
    status: BucketStatus = BucketStatus.ACTIVE

    owner_type: str = "system"
    owner_id: str | None = None

    created_by: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "buckets"
        indexes = [
            pymongo.IndexModel([("name", pymongo.ASCENDING)], unique=True),
            "status",
        ]
