from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models import ApiToken, Bucket
from app.modules.auth.dependencies import require_scope
from app.modules.buckets import service

router = APIRouter()


class CreateBucketRequest(BaseModel):
    name: str
    display_name: str | None = None
    visibility: str = "private"
    storage_backend: str = "minio"


class BucketView(BaseModel):
    id: str
    name: str
    display_name: str | None
    visibility: str
    storage_backend: str
    status: str

    @classmethod
    def of(cls, bucket: Bucket) -> "BucketView":
        return cls(
            id=str(bucket.id),
            name=bucket.name,
            display_name=bucket.display_name,
            visibility=bucket.visibility.value,
            storage_backend=bucket.storage_backend,
            status=bucket.status.value,
        )


@router.get("", response_model=list[BucketView])
async def list_buckets(_: ApiToken = Depends(require_scope("buckets:read"))):
    buckets = await service.list_buckets()
    return [BucketView.of(b) for b in buckets]


@router.post("", response_model=BucketView, status_code=201)
async def create_bucket(
    body: CreateBucketRequest,
    token: ApiToken = Depends(require_scope("buckets:write")),
):
    try:
        bucket = await service.create_bucket(
            name=body.name,
            display_name=body.display_name,
            visibility=body.visibility,
            storage_backend=body.storage_backend,
            created_by=f"token:{token.token_prefix}",
        )
    except service.BucketError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BucketView.of(bucket)


@router.get("/{bucket_name}", response_model=BucketView)
async def get_bucket(
    bucket_name: str,
    _: ApiToken = Depends(require_scope("buckets:read")),
):
    bucket = await service.get_by_name(bucket_name)
    if bucket is None:
        raise HTTPException(status_code=404, detail="Bucket not found")
    return BucketView.of(bucket)
