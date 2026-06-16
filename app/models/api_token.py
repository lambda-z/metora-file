from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field

from app.models.enums import ApiTokenStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApiToken(Document):
    name: str
    token_prefix: str
    token_hash: str

    owner_type: str = "system"
    owner_id: str | None = None

    scopes: list[str] = Field(default_factory=list)
    allowed_buckets: list[str] = Field(default_factory=list)

    status: ApiTokenStatus = ApiTokenStatus.ACTIVE

    created_by: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    class Settings:
        name = "api_tokens"
        indexes = [
            pymongo.IndexModel([("token_hash", pymongo.ASCENDING)], unique=True),
            "token_prefix",
            "status",
        ]
