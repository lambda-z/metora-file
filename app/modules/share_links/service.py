from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models import ShareLink, StoredObject
from app.models.enums import (
    ObjectStatus,
    SharePermission,
    ShareLinkStatus,
    ShareLinkVisibility,
)
from app.modules.audit import service as audit_service
from app.modules.auth import security
from app.modules.objects import service as object_service


class ShareLinkError(Exception):
    """Raised on share-link validation failures."""


@dataclass
class CreatedShareLink:
    share_link: ShareLink
    raw_token: str


@dataclass
class ResolvedShare:
    share_link: ShareLink
    object: StoredObject
    access_url: str


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def create_share_link(
    *,
    obj: StoredObject,
    visibility: str = "public",
    permission: str = "preview",
    password: str | None = None,
    expires_at: datetime | None = None,
    allow_download: bool = False,
    allow_preview: bool = True,
    max_access_count: int | None = None,
    created_by_type: str | None = None,
    created_by_id: str | None = None,
) -> CreatedShareLink:
    vis = ShareLinkVisibility(visibility)
    if vis == ShareLinkVisibility.PRIVATE and not password:
        raise ShareLinkError("Private share links require a password")

    raw_token = security.generate_share_token()
    share_link = ShareLink(
        object_id=obj.id,
        token_prefix=raw_token[:10],
        token_hash=security.hash_share_token(raw_token),
        visibility=vis,
        permission=SharePermission(permission),
        password_hash=security.hash_password(password) if password else None,
        allow_preview=allow_preview,
        allow_download=allow_download,
        expires_at=_aware(expires_at),
        max_access_count=max_access_count,
        created_by_type=created_by_type,
        created_by_id=created_by_id,
    )
    await share_link.insert()
    await audit_service.record(
        action="share_link.create",
        actor_type=created_by_type,
        actor_id=created_by_id,
        target_type="share_link",
        target_id=str(share_link.id),
        detail={"object_id": str(obj.id), "visibility": visibility},
    )
    return CreatedShareLink(share_link=share_link, raw_token=raw_token)


async def get_by_raw_token(raw_token: str) -> ShareLink | None:
    return await ShareLink.find_one(
        ShareLink.token_hash == security.hash_share_token(raw_token)
    )


def _ensure_usable(share_link: ShareLink) -> None:
    if share_link.status != ShareLinkStatus.ACTIVE:
        raise ShareLinkError("Share link is disabled")
    if share_link.expires_at and _aware(share_link.expires_at) < datetime.now(timezone.utc):
        raise ShareLinkError("Share link has expired")
    if (
        share_link.max_access_count is not None
        and share_link.access_count >= share_link.max_access_count
    ):
        raise ShareLinkError("Share link access limit reached")


async def _build_access(share_link: ShareLink) -> ResolvedShare:
    obj = await StoredObject.get(share_link.object_id)
    if obj is None or obj.status != ObjectStatus.ACTIVE:
        raise ShareLinkError("Shared object is no longer available")

    expires = 3600
    access_url = await object_service.generate_signed_url(obj=obj, expires_seconds=expires)

    share_link.access_count += 1
    share_link.last_accessed_at = datetime.now(timezone.utc)
    await share_link.save()

    return ResolvedShare(share_link=share_link, object=obj, access_url=access_url)


async def resolve_public_share(raw_token: str) -> ResolvedShare:
    share_link = await get_by_raw_token(raw_token)
    if share_link is None:
        raise ShareLinkError("Share link not found")
    _ensure_usable(share_link)
    if share_link.visibility == ShareLinkVisibility.PRIVATE:
        raise ShareLinkError("This share link requires a password")
    return await _build_access(share_link)


async def verify_private_share(*, raw_token: str, password: str) -> ResolvedShare | None:
    share_link = await get_by_raw_token(raw_token)
    if share_link is None:
        return None
    _ensure_usable(share_link)
    if not security.verify_password(password, share_link.password_hash or ""):
        return None
    return await _build_access(share_link)


async def disable_share_link(share_id: str) -> ShareLink | None:
    share_link = await ShareLink.get(share_id)
    if share_link is None:
        return None
    share_link.status = ShareLinkStatus.DISABLED
    await share_link.save()
    return share_link


async def list_share_links() -> list[ShareLink]:
    return await ShareLink.find_all().sort("-created_at").to_list()


async def list_for_object(object_id) -> list[ShareLink]:
    return await ShareLink.find(ShareLink.object_id == object_id).sort("-created_at").to_list()
