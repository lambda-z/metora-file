from __future__ import annotations

from app.models.api_token import ApiToken
from app.models.audit_log import AuditLog
from app.models.bucket import Bucket
from app.models.object_relation import ObjectRelation
from app.models.object_version import ObjectVersion
from app.models.share_link import ShareLink
from app.models.stored_object import StoredObject

ALL_DOCUMENT_MODELS = [
    Bucket,
    StoredObject,
    ObjectVersion,
    ObjectRelation,
    ApiToken,
    ShareLink,
    AuditLog,
]

__all__ = [
    "ApiToken",
    "AuditLog",
    "Bucket",
    "ObjectRelation",
    "ObjectVersion",
    "ShareLink",
    "StoredObject",
    "ALL_DOCUMENT_MODELS",
]
