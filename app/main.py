from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.admin.router import router as admin_router
from app.config import settings
from app.db.mongodb import close_mongodb, init_mongodb
from app.modules.auth.api import router as api_token_router
from app.modules.buckets.api import router as bucket_router
from app.modules.objects.api import router as object_router
from app.modules.relations.api import router as relation_router
from app.modules.share_links.api import router as share_link_router
from app.share.router import router as share_router
from app.templating import STATIC_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mongodb()
    yield
    await close_mongodb()


app = FastAPI(title="FileService", version="1.0.0", lifespan=lifespan)

# CORS: allow browsers on any (or configured) origin to call the API and the
# direct-upload endpoint (PUT /files/{key}). Credentials are disabled when
# allowing all origins, because the spec forbids `*` together with credentials
# (our browser flows use presigned query-string signatures / bearer tokens in
# headers, not cookies, so credentials are unnecessary).
_cors_origins = settings.cors_allow_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def index():
    return RedirectResponse(url="/admin")


# Admin UI (Basic Auth) + share access pages (token / signed)
app.include_router(admin_router)
app.include_router(share_router)

# REST API (API token auth)
app.include_router(api_token_router, prefix="/api/v1/api-tokens", tags=["api-tokens"])
app.include_router(bucket_router, prefix="/api/v1/buckets", tags=["buckets"])
app.include_router(object_router, prefix="/api/v1", tags=["objects"])
app.include_router(relation_router, prefix="/api/v1/object-relations", tags=["object-relations"])
app.include_router(share_link_router, prefix="/api/v1", tags=["share-links"])
