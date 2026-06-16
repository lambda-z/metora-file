from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Document):
    action: str
    actor_type: str | None = None
    actor_id: str | None = None

    target_type: str | None = None
    target_id: str | None = None

    detail: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "audit_logs"
        indexes = [
            "action",
            [("created_at", pymongo.DESCENDING)],
        ]
