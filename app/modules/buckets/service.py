from __future__ import annotations

from app.models import Bucket
from app.models.enums import BucketStatus, BucketVisibility
from app.modules.audit import service as audit_service


class BucketError(Exception):
    """Raised on bucket validation failures (e.g. duplicate name)."""


async def create_bucket(
    *,
    name: str,
    display_name: str | None = None,
    visibility: str = "private",
    storage_backend: str = "minio",
    owner_type: str = "system",
    owner_id: str | None = None,
    created_by: str | None = None,
) -> Bucket:
    existing = await Bucket.find_one(Bucket.name == name)
    if existing:
        raise BucketError("Bucket already exists")

    bucket = Bucket(
        name=name,
        display_name=display_name,
        visibility=BucketVisibility(visibility),
        storage_backend=storage_backend,
        owner_type=owner_type,
        owner_id=owner_id,
        created_by=created_by,
    )
    await bucket.insert()
    await audit_service.record(
        action="bucket.create",
        actor_type=owner_type,
        actor_id=created_by,
        target_type="bucket",
        target_id=str(bucket.id),
        detail={"name": name},
    )
    return bucket


async def list_buckets(active_only: bool = False) -> list[Bucket]:
    if active_only:
        return await Bucket.find(Bucket.status == BucketStatus.ACTIVE).sort("-created_at").to_list()
    return await Bucket.find_all().sort("-created_at").to_list()


async def get_active_buckets() -> list[Bucket]:
    return await Bucket.find(Bucket.status == BucketStatus.ACTIVE).to_list()


async def get_by_name(name: str) -> Bucket | None:
    return await Bucket.find_one(Bucket.name == name)
