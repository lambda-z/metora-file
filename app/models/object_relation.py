from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ObjectRelation(Document):
    object_id: PydanticObjectId
    relation_type: str

    target_type: str | None = None
    target_id: str | None = None

    note: str | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "object_relations"
        indexes = [
            "object_id",
            [("target_type", pymongo.ASCENDING), ("target_id", pymongo.ASCENDING)],
        ]
