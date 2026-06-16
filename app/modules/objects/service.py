from __future__ import annotations

from datetime import datetime, timezone

from app.models import Bucket, ObjectVersion, StoredObject
from app.models.enums import ObjectStatus, ObjectVisibility
from app.modules.audit import service as audit_service
from app.storage import get_storage_backend


class ObjectError(Exception):
    """Raised on object-service validation failures."""


async def upload_object(
    *,
    bucket: Bucket,
    data: bytes,
    filename: str,
    content_type: str | None = None,
    object_key: str | None = None,
    visibility: str = "private",
    source_system: str | None = "admin-ui",
    owner_type: str | None = None,
    owner_id: str | None = None,
    uploader_type: str | None = None,
    uploader_id: str | None = None,
) -> StoredObject:
    """Store a file body in the storage backend and persist its metadata.

    The single source of truth for uploads — both the REST API and the admin UI
    call this. File bytes go to storage; MongoDB only keeps metadata.
    """
    storage = get_storage_backend()
    storage_key = storage.build_key(
        bucket=bucket.name, object_key=object_key, filename=filename
    )
    meta = storage.put_object(key=storage_key, data=data, content_type=content_type)

    obj = StoredObject(
        bucket_name=bucket.name,
        object_key=object_key or storage_key,
        storage_key=storage_key,
        filename=filename,
        content_type=content_type,
        size=meta.get("size", len(data)),
        etag=meta.get("etag"),
        visibility=ObjectVisibility(visibility),
        status=ObjectStatus.ACTIVE,
        source_system=source_system,
        owner_type=owner_type,
        owner_id=owner_id,
        uploader_type=uploader_type,
        uploader_id=uploader_id,
        current_generation=1,
    )
    await obj.insert()

    version = ObjectVersion(
        object_id=obj.id,
        generation=1,
        storage_key=storage_key,
        size=obj.size,
        content_type=content_type,
        etag=obj.etag,
        uploader_type=uploader_type,
        uploader_id=uploader_id,
    )
    await version.insert()

    await audit_service.record(
        action="object.upload",
        actor_type=uploader_type,
        actor_id=uploader_id,
        target_type="object",
        target_id=str(obj.id),
        detail={"bucket": bucket.name, "key": obj.object_key, "size": obj.size},
    )
    return obj


async def generate_signed_url(*, obj: StoredObject, expires_seconds: int = 300) -> str:
    storage = get_storage_backend()
    return storage.get_download_url(
        key=obj.storage_key,
        expires=expires_seconds,
        filename=obj.filename,
    )


async def soft_delete(*, obj: StoredObject, actor_id: str | None = None) -> StoredObject:
    obj.status = ObjectStatus.DELETED
    obj.deleted_at = datetime.now(timezone.utc)
    await obj.save()
    await audit_service.record(
        action="object.delete",
        actor_id=actor_id,
        target_type="object",
        target_id=str(obj.id),
    )
    return obj


async def query_objects(
    *,
    bucket_name: str | None = None,
    source_system: str | None = None,
    owner_type: str | None = None,
    owner_id: str | None = None,
    include_deleted: bool = False,
) -> list[StoredObject]:
    filters = []
    if bucket_name:
        filters.append(StoredObject.bucket_name == bucket_name)
    if source_system:
        filters.append(StoredObject.source_system == source_system)
    if owner_type:
        filters.append(StoredObject.owner_type == owner_type)
    if owner_id:
        filters.append(StoredObject.owner_id == owner_id)
    if not include_deleted:
        filters.append(StoredObject.status == ObjectStatus.ACTIVE)
    return await StoredObject.find(*filters).sort("-created_at").to_list()


async def get_object(object_id: str) -> StoredObject | None:
    return await StoredObject.get(object_id)
