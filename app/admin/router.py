from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.models import ApiToken, Bucket, ObjectVersion, ShareLink, StoredObject
from app.models.enums import AVAILABLE_SCOPES
from app.admin.dependencies import require_admin
from app.modules.audit import service as audit_service
from app.modules.auth import service as token_service
from app.modules.buckets import service as bucket_service
from app.modules.objects import service as object_service
from app.modules.relations import service as relation_service
from app.modules.share_links import service as share_service
from app.templating import template_response

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


def _ctx(request: Request, **extra) -> dict:
    return {"request": request, "settings": settings, **extra}


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    bucket_count = await Bucket.find_all().count()
    object_count = await StoredObject.find_all().count()
    token_count = await ApiToken.find_all().count()
    share_link_count = await ShareLink.find_all().count()
    recent_objects = await StoredObject.find_all().sort("-created_at").limit(10).to_list()
    recent_audits = await audit_service.recent(10)
    return template_response(
        "admin/dashboard.html",
        _ctx(
            request,
            bucket_count=bucket_count,
            object_count=object_count,
            token_count=token_count,
            share_link_count=share_link_count,
            recent_objects=recent_objects,
            recent_audits=recent_audits,
        ),
    )


# --------------------------------------------------------------------------- #
# API Tokens
# --------------------------------------------------------------------------- #
@router.get("/api-tokens", response_class=HTMLResponse)
async def api_tokens(request: Request):
    tokens = await token_service.list_tokens()
    return template_response(
        "admin/api_tokens/list.html", _ctx(request, tokens=tokens)
    )


@router.get("/api-tokens/new", response_class=HTMLResponse)
async def new_api_token(request: Request):
    buckets = await bucket_service.get_active_buckets()
    return template_response(
        "admin/api_tokens/new.html",
        _ctx(request, buckets=buckets, available_scopes=AVAILABLE_SCOPES),
    )


@router.post("/api-tokens", response_class=HTMLResponse)
async def create_api_token(
    request: Request,
    name: str = Form(...),
    owner_type: str = Form("system"),
    owner_id: str | None = Form(None),
    scopes: list[str] = Form(default=[]),
    allowed_buckets: list[str] = Form(default=[]),
):
    created = await token_service.create_token(
        name=name,
        owner_type=owner_type,
        owner_id=owner_id or None,
        scopes=scopes,
        allowed_buckets=allowed_buckets,
        env=settings.api_token_env,
        created_by="admin-ui",
    )
    return template_response(
        "admin/api_tokens/created.html",
        _ctx(request, token=created.token, raw_token=created.raw_token),
    )


@router.post("/api-tokens/{token_id}/revoke")
async def revoke_api_token(token_id: str):
    token = await token_service.revoke_token(token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="API token not found")
    return RedirectResponse(url="/admin/api-tokens", status_code=303)


# --------------------------------------------------------------------------- #
# Buckets
# --------------------------------------------------------------------------- #
@router.get("/buckets", response_class=HTMLResponse)
async def buckets(request: Request):
    items = await bucket_service.list_buckets()
    return template_response("admin/buckets/list.html", _ctx(request, buckets=items))


@router.get("/buckets/new", response_class=HTMLResponse)
async def new_bucket(request: Request):
    return template_response("admin/buckets/new.html", _ctx(request))


@router.post("/buckets")
async def create_bucket(
    name: str = Form(...),
    display_name: str | None = Form(None),
    visibility: str = Form("private"),
    storage_backend: str = Form("minio"),
):
    try:
        await bucket_service.create_bucket(
            name=name,
            display_name=display_name or None,
            visibility=visibility,
            storage_backend=storage_backend,
            created_by="admin-ui",
        )
    except bucket_service.BucketError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/admin/buckets", status_code=303)


@router.get("/buckets/{bucket_name}", response_class=HTMLResponse)
async def bucket_detail(request: Request, bucket_name: str):
    bucket = await bucket_service.get_by_name(bucket_name)
    if bucket is None:
        raise HTTPException(status_code=404, detail="Bucket not found")
    objects = await object_service.query_objects(bucket_name=bucket_name)
    return template_response(
        "admin/buckets/detail.html", _ctx(request, bucket=bucket, objects=objects)
    )


@router.post("/buckets/{bucket_name}/objects")
async def upload_object(
    bucket_name: str,
    file: UploadFile = File(...),
    object_key: str | None = Form(None),
    visibility: str = Form("private"),
    source_system: str | None = Form("admin-ui"),
    owner_type: str | None = Form(None),
    owner_id: str | None = Form(None),
):
    bucket = await bucket_service.get_by_name(bucket_name)
    if bucket is None:
        raise HTTPException(status_code=404, detail="Bucket not found")
    data = await file.read()
    # Reuse ObjectService — no upload logic is duplicated in the router.
    await object_service.upload_object(
        bucket=bucket,
        data=data,
        filename=file.filename or "file",
        content_type=file.content_type,
        object_key=object_key or None,
        visibility=visibility,
        source_system=source_system,
        owner_type=owner_type or None,
        owner_id=owner_id or None,
        uploader_type="admin",
        uploader_id="admin-ui",
    )
    return RedirectResponse(url=f"/admin/buckets/{bucket_name}", status_code=303)


# --------------------------------------------------------------------------- #
# Objects
# --------------------------------------------------------------------------- #
@router.get("/objects", response_class=HTMLResponse)
async def objects(
    request: Request,
    bucket_name: str | None = None,
    source_system: str | None = None,
    owner_type: str | None = None,
    owner_id: str | None = None,
):
    items = await object_service.query_objects(
        bucket_name=bucket_name,
        source_system=source_system,
        owner_type=owner_type,
        owner_id=owner_id,
    )
    return template_response(
        "admin/objects/list.html",
        _ctx(
            request,
            objects=items,
            filters={
                "bucket_name": bucket_name or "",
                "source_system": source_system or "",
                "owner_type": owner_type or "",
                "owner_id": owner_id or "",
            },
        ),
    )


async def _object_detail_context(request: Request, obj: StoredObject, **extra) -> dict:
    versions = (
        await ObjectVersion.find(ObjectVersion.object_id == obj.id)
        .sort("-generation")
        .to_list()
    )
    relations = await relation_service.list_for_object(str(obj.id))
    share_links = await share_service.list_for_object(obj.id)
    return _ctx(
        request,
        object=obj,
        versions=versions,
        relations=relations,
        share_links=share_links,
        **extra,
    )


@router.get("/objects/{object_id}", response_class=HTMLResponse)
async def object_detail(request: Request, object_id: str):
    obj = await object_service.get_object(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    ctx = await _object_detail_context(request, obj)
    return template_response("admin/objects/detail.html", ctx)


@router.post("/objects/{object_id}/signed-url", response_class=HTMLResponse)
async def generate_signed_url(
    request: Request,
    object_id: str,
    expires_seconds: int = Form(300),
):
    obj = await object_service.get_object(object_id)
    if obj is None or obj.status.value != "active":
        raise HTTPException(status_code=404, detail="Object not found")
    url = await object_service.generate_signed_url(obj=obj, expires_seconds=expires_seconds)
    ctx = await _object_detail_context(request, obj, signed_url=url)
    return template_response("admin/objects/detail.html", ctx)


@router.post("/objects/{object_id}/delete")
async def delete_object(object_id: str):
    obj = await object_service.get_object(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    await object_service.soft_delete(obj=obj, actor_id="admin-ui")
    return RedirectResponse(url=f"/admin/buckets/{obj.bucket_name}", status_code=303)


# --------------------------------------------------------------------------- #
# Share links
# --------------------------------------------------------------------------- #
@router.get("/share-links", response_class=HTMLResponse)
async def share_links(request: Request):
    links = await share_service.list_share_links()
    object_ids = [link.object_id for link in links]
    objects = (
        await StoredObject.find({"_id": {"$in": object_ids}}).to_list() if object_ids else []
    )
    object_map = {str(obj.id): obj for obj in objects}
    return template_response(
        "admin/share_links/list.html",
        _ctx(request, share_links=links, object_map=object_map),
    )


@router.get("/objects/{object_id}/share-links/new", response_class=HTMLResponse)
async def new_share_link(request: Request, object_id: str):
    obj = await object_service.get_object(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return template_response(
        "admin/share_links/new.html", _ctx(request, object=obj)
    )


@router.post("/objects/{object_id}/share-links", response_class=HTMLResponse)
async def create_share_link(
    request: Request,
    object_id: str,
    visibility: str = Form("public"),
    permission: str = Form("preview"),
    password: str | None = Form(None),
    expires_at: str | None = Form(None),
    allow_download: bool = Form(False),
    allow_preview: bool = Form(True),
    max_access_count: int | None = Form(None),
):
    obj = await object_service.get_object(object_id)
    if obj is None or obj.status.value != "active":
        raise HTTPException(status_code=404, detail="Object not found")

    parsed_expires: datetime | None = None
    if expires_at:
        try:
            parsed_expires = datetime.fromisoformat(expires_at)
        except ValueError:
            parsed_expires = None

    try:
        created = await share_service.create_share_link(
            obj=obj,
            visibility=visibility,
            permission=permission,
            password=(password or None),
            expires_at=parsed_expires,
            allow_download=allow_download,
            allow_preview=allow_preview,
            max_access_count=max_access_count,
            created_by_type="admin",
            created_by_id="admin-ui",
        )
    except share_service.ShareLinkError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    share_url = f"{settings.base_url.rstrip('/')}/share/{created.raw_token}"
    ctx = await _object_detail_context(
        request,
        obj,
        new_share_link=created.share_link,
        new_share_url=share_url,
    )
    return template_response("admin/objects/detail.html", ctx)


@router.post("/share-links/{share_id}/disable")
async def disable_share_link(share_id: str):
    link = await share_service.disable_share_link(share_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    return RedirectResponse(url="/admin/share-links", status_code=303)
