from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models import ApiToken, ShareLink
from app.modules.auth.dependencies import require_scope
from app.modules.objects import service as object_service
from app.modules.share_links import service

router = APIRouter()


class CreateShareLinkRequest(BaseModel):
    visibility: str = "public"
    permission: str = "preview"
    password: str | None = None
    expires_at: datetime | None = None
    allow_download: bool = False
    allow_preview: bool = True
    max_access_count: int | None = None


class ShareLinkView(BaseModel):
    id: str
    object_id: str
    visibility: str
    permission: str
    allow_preview: bool
    allow_download: bool
    status: str
    access_count: int
    max_access_count: int | None

    @classmethod
    def of(cls, link: ShareLink) -> "ShareLinkView":
        return cls(
            id=str(link.id),
            object_id=str(link.object_id),
            visibility=link.visibility.value,
            permission=link.permission.value,
            allow_preview=link.allow_preview,
            allow_download=link.allow_download,
            status=link.status.value,
            access_count=link.access_count,
            max_access_count=link.max_access_count,
        )


class CreateShareLinkResponse(ShareLinkView):
    raw_token: str
    share_url: str


@router.get("/share-links", response_model=list[ShareLinkView])
async def list_share_links(_: ApiToken = Depends(require_scope("share-links:read"))):
    links = await service.list_share_links()
    return [ShareLinkView.of(link) for link in links]


@router.post(
    "/objects/{object_id}/share-links",
    response_model=CreateShareLinkResponse,
    status_code=201,
)
async def create_share_link(
    object_id: str,
    body: CreateShareLinkRequest,
    token: ApiToken = Depends(require_scope("share-links:write")),
):
    from app.config import settings

    obj = await object_service.get_object(object_id)
    if obj is None or obj.status.value != "active":
        raise HTTPException(status_code=404, detail="Object not found")
    try:
        created = await service.create_share_link(
            obj=obj,
            visibility=body.visibility,
            permission=body.permission,
            password=body.password,
            expires_at=body.expires_at,
            allow_download=body.allow_download,
            allow_preview=body.allow_preview,
            max_access_count=body.max_access_count,
            created_by_type="api",
            created_by_id=f"token:{token.token_prefix}",
        )
    except service.ShareLinkError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    view = ShareLinkView.of(created.share_link)
    share_url = f"{settings.base_url.rstrip('/')}/share/{created.raw_token}"
    return CreateShareLinkResponse(
        raw_token=created.raw_token, share_url=share_url, **view.model_dump()
    )


@router.post("/share-links/{share_id}/disable", response_model=ShareLinkView)
async def disable_share_link(
    share_id: str,
    _: ApiToken = Depends(require_scope("share-links:write")),
):
    link = await service.disable_share_link(share_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    return ShareLinkView.of(link)
