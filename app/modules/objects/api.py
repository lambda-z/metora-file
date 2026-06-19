from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.models import ApiToken, StoredObject
from app.modules.auth.dependencies import ensure_bucket_allowed, require_scope
from app.modules.buckets import service as bucket_service
from app.modules.objects import service

router = APIRouter()


class ObjectView(BaseModel):
    id: str
    bucket_name: str
    object_key: str
    folder: str
    filename: str | None
    content_type: str | None
    size: int
    visibility: str
    status: str
    source_system: str | None
    owner_type: str | None
    owner_id: str | None

    @classmethod
    def of(cls, obj: StoredObject) -> "ObjectView":
        return cls(
            id=str(obj.id),
            bucket_name=obj.bucket_name,
            object_key=obj.object_key,
            folder=obj.folder,
            filename=obj.filename,
            content_type=obj.content_type,
            size=obj.size,
            visibility=obj.visibility.value,
            status=obj.status.value,
            source_system=obj.source_system,
            owner_type=obj.owner_type,
            owner_id=obj.owner_id,
        )


class SignedUrlResponse(BaseModel):
    url: str
    expires_seconds: int


class InitUploadRequest(BaseModel):
    filename: str
    content_type: str | None = None
    object_key: str | None = None
    folder: str | None = None
    visibility: str = "private"
    source_system: str | None = "api"
    owner_type: str | None = None
    owner_id: str | None = None
    expires_seconds: int = 300


class UploadInstructions(BaseModel):
    url: str
    method: str
    headers: dict[str, str] = {}
    expires_seconds: int


class InitUploadResponse(BaseModel):
    object_id: str
    storage_key: str
    upload: UploadInstructions


class ConfirmUploadRequest(BaseModel):
    size: int | None = None
    etag: str | None = None


@router.get("/objects", response_model=list[ObjectView])
async def list_objects(
    bucket_name: str | None = None,
    folder: str | None = None,
    source_system: str | None = None,
    owner_type: str | None = None,
    owner_id: str | None = None,
    _: ApiToken = Depends(require_scope("objects:read")),
):
    objects = await service.query_objects(
        bucket_name=bucket_name,
        folder=folder,
        source_system=source_system,
        owner_type=owner_type,
        owner_id=owner_id,
    )
    return [ObjectView.of(o) for o in objects]


@router.get("/objects/{object_id}", response_model=ObjectView)
async def get_object(
    object_id: str,
    _: ApiToken = Depends(require_scope("objects:read")),
):
    obj = await service.get_object(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return ObjectView.of(obj)


@router.post("/buckets/{bucket_name}/objects", response_model=ObjectView, status_code=201)
async def upload_object(
    bucket_name: str,
    file: UploadFile = File(...),
    object_key: str | None = Form(None),
    folder: str | None = Form(None),
    visibility: str = Form("private"),
    source_system: str | None = Form("api"),
    owner_type: str | None = Form(None),
    owner_id: str | None = Form(None),
    token: ApiToken = Depends(require_scope("objects:write")),
):
    ensure_bucket_allowed(token, bucket_name)
    bucket = await bucket_service.get_by_name(bucket_name)
    if bucket is None:
        raise HTTPException(status_code=404, detail="Bucket not found")
    data = await file.read()
    obj = await service.upload_object(
        bucket=bucket,
        data=data,
        filename=file.filename or "file",
        content_type=file.content_type,
        object_key=object_key,
        folder=folder,
        visibility=visibility,
        source_system=source_system,
        owner_type=owner_type,
        owner_id=owner_id,
        uploader_type="api",
        uploader_id=f"token:{token.token_prefix}",
    )
    return ObjectView.of(obj)


@router.post(
    "/buckets/{bucket_name}/objects/init-upload",
    response_model=InitUploadResponse,
    status_code=201,
)
async def init_object_upload(
    bucket_name: str,
    body: InitUploadRequest,
    token: ApiToken = Depends(require_scope("objects:write")),
):
    ensure_bucket_allowed(token, bucket_name)
    bucket = await bucket_service.get_by_name(bucket_name)
    if bucket is None:
        raise HTTPException(status_code=404, detail="Bucket not found")
    obj, upload = await service.init_upload(
        bucket=bucket,
        filename=body.filename,
        content_type=body.content_type,
        object_key=body.object_key,
        folder=body.folder,
        visibility=body.visibility,
        source_system=body.source_system,
        owner_type=body.owner_type,
        owner_id=body.owner_id,
        uploader_type="api",
        uploader_id=f"token:{token.token_prefix}",
        expires_seconds=body.expires_seconds,
    )
    return InitUploadResponse(
        object_id=str(obj.id),
        storage_key=obj.storage_key,
        upload=UploadInstructions(
            url=upload["url"],
            method=upload.get("method", "PUT"),
            headers=upload.get("headers", {}),
            expires_seconds=body.expires_seconds,
        ),
    )


@router.post("/objects/{object_id}/confirm-upload", response_model=ObjectView)
async def confirm_object_upload(
    object_id: str,
    body: ConfirmUploadRequest | None = None,
    _: ApiToken = Depends(require_scope("objects:write")),
):
    obj = await service.get_object(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    body = body or ConfirmUploadRequest()
    try:
        obj = await service.confirm_upload(obj=obj, size=body.size, etag=body.etag)
    except service.ObjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ObjectView.of(obj)


@router.post("/objects/{object_id}/signed-url", response_model=SignedUrlResponse)
async def create_signed_url(
    object_id: str,
    expires_seconds: int = Form(300),
    _: ApiToken = Depends(require_scope("objects:read")),
):
    obj = await service.get_object(object_id)
    if obj is None or obj.status.value != "active":
        raise HTTPException(status_code=404, detail="Object not found")
    url = await service.generate_signed_url(obj=obj, expires_seconds=expires_seconds)
    return SignedUrlResponse(url=url, expires_seconds=expires_seconds)


@router.delete("/objects/{object_id}", status_code=204)
async def delete_object(
    object_id: str,
    token: ApiToken = Depends(require_scope("objects:delete")),
):
    obj = await service.get_object(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    await service.soft_delete(obj=obj, actor_id=f"token:{token.token_prefix}")
