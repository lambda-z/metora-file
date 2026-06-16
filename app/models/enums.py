from __future__ import annotations

from enum import Enum


class BucketStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class BucketVisibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class ObjectStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class ObjectVisibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class ApiTokenStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ShareLinkStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ShareLinkVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class SharePermission(str, Enum):
    PREVIEW = "preview"
    DOWNLOAD = "download"


# Scopes available when creating an API token.
AVAILABLE_SCOPES: list[str] = [
    "buckets:read",
    "buckets:write",
    "objects:read",
    "objects:write",
    "objects:delete",
    "share-links:read",
    "share-links:write",
    "relations:read",
    "relations:write",
]
