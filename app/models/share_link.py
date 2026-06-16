from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import Field

from app.models.enums import SharePermission, ShareLinkStatus, ShareLinkVisibility


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShareLink(Document):
    object_id: PydanticObjectId
    token_prefix: str
    token_hash: str

    visibility: ShareLinkVisibility = ShareLinkVisibility.PUBLIC
    permission: SharePermission = SharePermission.PREVIEW
    password_hash: str | None = None

    allow_preview: bool = True
    allow_download: bool = False

    expires_at: datetime | None = None
    max_access_count: int | None = None
    access_count: int = 0

    status: ShareLinkStatus = ShareLinkStatus.ACTIVE

    created_by_type: str | None = None
    created_by_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    last_accessed_at: datetime | None = None

    class Settings:
        name = "share_links"
        indexes = [
            pymongo.IndexModel([("token_hash", pymongo.ASCENDING)], unique=True),
            "object_id",
            "status",
        ]
