from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from app.models import StoredObject
from app.models.enums import ObjectStatus, ObjectVisibility
from app.modules.objects import service as object_service
from app.modules.share_links import service as share_service
from app.storage import get_storage_backend
from app.storage.signing import verify_signature
from app.templating import templates

router = APIRouter()


def _stream(key: str, content_type: str | None, filename: str | None) -> StreamingResponse:
    storage = get_storage_backend()
    stream = storage.open_stream(key=key)
    headers = {}
    if filename:
        headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return StreamingResponse(
        stream,
        media_type=content_type or "application/octet-stream",
        headers=headers,
    )


# --------------------------------------------------------------------------- #
# Signed local download endpoint (used by LocalBackend.get_download_url)
# --------------------------------------------------------------------------- #
@router.get("/files/{key:path}")
async def serve_local_file(
    key: str,
    expires: int = Query(...),
    sig: str = Query(...),
    filename: str | None = Query(None),
):
    if not verify_signature(key, expires, sig):
        raise HTTPException(status_code=403, detail="Invalid or expired signature")
    obj = await StoredObject.find_one(StoredObject.storage_key == key)
    content_type = obj.content_type if obj else None
    display_name = filename or (obj.filename if obj else None)
    try:
        return _stream(key, content_type, display_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc


# --------------------------------------------------------------------------- #
# Public object access (only objects whose visibility is public)
# --------------------------------------------------------------------------- #
@router.get("/public/objects/{object_id}")
async def public_object(object_id: str):
    obj = await object_service.get_object(object_id)
    if (
        obj is None
        or obj.status != ObjectStatus.ACTIVE
        or obj.visibility != ObjectVisibility.PUBLIC
    ):
        raise HTTPException(status_code=404, detail="Object not found")
    url = await object_service.generate_signed_url(obj=obj, expires_seconds=300)
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=url, status_code=307)


# --------------------------------------------------------------------------- #
# Share link access pages
# --------------------------------------------------------------------------- #
@router.get("/share/{token}", response_class=HTMLResponse)
async def share_entry(request: Request, token: str):
    share_link = await share_service.get_by_raw_token(token)
    if share_link is None:
        raise HTTPException(status_code=404, detail="Share link not found")

    if share_link.visibility.value == "private" and share_link.password_hash:
        return templates.TemplateResponse(
            "share/private.html", {"request": request, "token": token}
        )

    try:
        result = await share_service.resolve_public_share(token)
    except share_service.ShareLinkError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return templates.TemplateResponse(
        "share/public.html",
        {
            "request": request,
            "share_link": result.share_link,
            "object": result.object,
            "access_url": result.access_url,
        },
    )


@router.post("/share/{token}/verify", response_class=HTMLResponse)
async def verify_private(request: Request, token: str, password: str = Form(...)):
    result = await share_service.verify_private_share(raw_token=token, password=password)
    if result is None:
        return templates.TemplateResponse(
            "share/private.html",
            {"request": request, "token": token, "error": "Invalid password"},
            status_code=401,
        )
    return templates.TemplateResponse(
        "share/verified.html",
        {
            "request": request,
            "share_link": result.share_link,
            "object": result.object,
            "access_url": result.access_url,
        },
    )
