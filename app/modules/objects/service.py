from __future__ import annotations

from datetime import datetime, timezone

from app.models import Bucket, ObjectVersion, StoredObject
from app.models.enums import ObjectStatus, ObjectVisibility
from app.modules.audit import service as audit_service
from app.storage import get_storage_backend, normalize_folder


class ObjectError(Exception):
    """Raised on object-service validation failures."""


async def upload_object(
    *,
    bucket: Bucket,
    data: bytes,
    filename: str,
    content_type: str | None = None,
    object_key: str | None = None,
    folder: str | None = None,
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

    ``folder`` is an optional bucket-relative folder path; it is prefixed onto
    the storage key so the path and download URL reflect the folder.
    """
    storage = get_storage_backend()
    folder = normalize_folder(folder)
    storage_key = storage.build_key(
        bucket=bucket.name, object_key=object_key, filename=filename, folder=folder
    )
    meta = storage.put_object(key=storage_key, data=data, content_type=content_type)

    obj = StoredObject(
        bucket_name=bucket.name,
        object_key=object_key or storage_key,
        storage_key=storage_key,
        folder=folder,
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


async def init_upload(
    *,
    bucket: Bucket,
    filename: str,
    content_type: str | None = None,
    object_key: str | None = None,
    folder: str | None = None,
    visibility: str = "private",
    source_system: str | None = "api",
    owner_type: str | None = None,
    owner_id: str | None = None,
    uploader_type: str | None = None,
    uploader_id: str | None = None,
    expires_seconds: int = 300,
) -> tuple[StoredObject, dict]:
    """Phase 1 of presigned direct upload.

    Pre-creates a ``PENDING`` metadata record (no bytes written) and returns
    presigned PUT instructions so the client uploads straight to storage. The
    caller must invoke :func:`confirm_upload` once the bytes are uploaded.

    ``folder`` is an optional bucket-relative folder path; it is prefixed onto
    the storage key so the path and presigned URL reflect the folder.
    """
    storage = get_storage_backend()
    folder = normalize_folder(folder)
    storage_key = storage.build_key(
        bucket=bucket.name, object_key=object_key, filename=filename, folder=folder
    )
    obj = StoredObject(
        bucket_name=bucket.name,
        object_key=object_key or storage_key,
        storage_key=storage_key,
        folder=folder,
        filename=filename,
        content_type=content_type,
        size=0,
        etag=None,
        visibility=ObjectVisibility(visibility),
        status=ObjectStatus.PENDING,
        source_system=source_system,
        owner_type=owner_type,
        owner_id=owner_id,
        uploader_type=uploader_type,
        uploader_id=uploader_id,
        current_generation=1,
    )
    await obj.insert()

    upload = storage.presigned_put_url(
        key=storage_key, expires=expires_seconds, content_type=content_type
    )

    await audit_service.record(
        action="object.init_upload",
        actor_type=uploader_type,
        actor_id=uploader_id,
        target_type="object",
        target_id=str(obj.id),
        detail={"bucket": bucket.name, "key": obj.object_key},
    )
    return obj, upload


async def confirm_upload(
    *, obj: StoredObject, size: int | None = None, etag: str | None = None
) -> StoredObject:
    """Phase 2 of presigned direct upload.

    Verifies the body exists in storage, backfills size/etag, flips the object to
    ``ACTIVE`` and records the first version + audit entry.
    """
    storage = get_storage_backend()
    if size is None or etag is None:
        try:
            meta = storage.stat_object(key=obj.storage_key)
        except FileNotFoundError as exc:
            raise ObjectError("Uploaded object body not found in storage") from exc
        size = meta.get("size", 0) if size is None else size
        etag = meta.get("etag") if etag is None else etag

    obj.size = size
    obj.etag = etag
    obj.status = ObjectStatus.ACTIVE
    obj.updated_at = datetime.now(timezone.utc)
    await obj.save()

    version = ObjectVersion(
        object_id=obj.id,
        generation=obj.current_generation,
        storage_key=obj.storage_key,
        size=size,
        content_type=obj.content_type,
        etag=etag,
        uploader_type=obj.uploader_type,
        uploader_id=obj.uploader_id,
    )
    await version.insert()

    await audit_service.record(
        action="object.upload",
        actor_type=obj.uploader_type,
        actor_id=obj.uploader_id,
        target_type="object",
        target_id=str(obj.id),
        detail={"bucket": obj.bucket_name, "key": obj.object_key, "size": size},
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
    folder: str | None = None,
    source_system: str | None = None,
    owner_type: str | None = None,
    owner_id: str | None = None,
    include_deleted: bool = False,
) -> list[StoredObject]:
    filters = []
    if bucket_name:
        filters.append(StoredObject.bucket_name == bucket_name)
    if folder is not None:
        filters.append(StoredObject.folder == normalize_folder(folder))
    if source_system:
        filters.append(StoredObject.source_system == source_system)
    if owner_type:
        filters.append(StoredObject.owner_type == owner_type)
    if owner_id:
        filters.append(StoredObject.owner_id == owner_id)
    if not include_deleted:
        filters.append(StoredObject.status == ObjectStatus.ACTIVE)
    # Folder markers are virtual placeholders, never real files — hide them.
    # ``!= True`` matches both ``false`` and legacy docs missing the field.
    filters.append(StoredObject.is_placeholder != True)  # noqa: E712
    return await StoredObject.find(*filters).sort("-created_at").to_list()


async def create_folder(
    *,
    bucket_name: str,
    name: str,
    parent: str | None = None,
    created_by: str = "admin-ui",
) -> str:
    """Create a virtual folder under ``parent`` so it persists while empty.

    Folders are virtual prefixes derived from object metadata. To let an *empty*
    folder exist, we insert a lightweight placeholder marker (no bytes) carrying
    the folder path. Real uploads and listings ignore markers. Idempotent: if the
    folder already contains anything (a marker or a real object), nothing happens.

    Returns the normalised full folder path (e.g. ``images/2024``).
    """
    parent_norm = normalize_folder(parent)
    combined = f"{parent_norm}/{name}" if parent_norm else name
    folder = normalize_folder(combined)
    if not folder:
        raise ObjectError("Folder name is required")

    existing = await StoredObject.find_one(
        StoredObject.bucket_name == bucket_name,
        StoredObject.folder == folder,
        StoredObject.status == ObjectStatus.ACTIVE,
    )
    if existing is not None:
        return folder

    marker = StoredObject(
        bucket_name=bucket_name,
        object_key=f".folder/{folder}",
        storage_key="",
        folder=folder,
        is_placeholder=True,
        filename=None,
        status=ObjectStatus.ACTIVE,
        source_system="admin-ui",
    )
    await marker.insert()
    await audit_service.record(
        action="folder.create",
        actor_id=created_by,
        target_type="folder",
        target_id=f"{bucket_name}/{folder}",
        detail={"bucket": bucket_name, "folder": folder},
    )
    return folder


async def list_folders(*, bucket_name: str, parent: str | None = None) -> list[str]:
    """List immediate sub-folder names directly under ``parent`` in a bucket.

    Folders are virtual: derived from the ``folder`` of active objects. Passing
    ``parent=None`` (or "") lists the top-level folders; passing ``a/b`` lists
    the direct children of ``a/b``. Returns just the child segment names, sorted.
    """
    parent = normalize_folder(parent)
    prefix = f"{parent}/" if parent else ""

    folders = await StoredObject.get_pymongo_collection().distinct(
        "folder",
        {"bucket_name": bucket_name, "status": ObjectStatus.ACTIVE.value},
    )

    children: set[str] = set()
    for raw in folders:
        folder = raw or ""
        if not folder or not folder.startswith(prefix):
            continue
        remainder = folder[len(prefix):]
        if not remainder:
            continue
        children.add(remainder.split("/", 1)[0])
    return sorted(children)


async def get_object(object_id: str) -> StoredObject | None:
    return await StoredObject.get(object_id)
