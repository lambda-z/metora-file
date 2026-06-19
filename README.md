# FileService

Standalone file service for Metora: **MongoDB + Beanie** metadata, **MinIO** (or
local-disk fallback) object storage, and a **FastAPI** app that serves both a REST
API and a lightweight Jinja2/HTMX admin UI plus share-access pages.

- File bytes live in the storage backend (MinIO / local disk) — **never** in MongoDB.
- MongoDB stores only metadata (`Bucket`, `StoredObject`, `ObjectVersion`,
  `ObjectRelation`, `ApiToken`, `ShareLink`, `AuditLog`).
- API tokens are stored as a sha256 hash + prefix; the raw token is shown **once**.

## Layout

```
app/
├── main.py            # FastAPI app, lifespan, router wiring
├── config.py          # pydantic-settings (env / .env)
├── db/mongodb.py      # motor client + init_beanie
├── models/            # Beanie documents + enums
├── storage/           # StorageBackend (base/local/minio/factory) + signed URLs
├── modules/           # auth, buckets, objects, relations, share_links, audit
├── admin/             # /admin/* router + Basic-Auth dependency
├── share/             # /share/{token}, /files/{key}, /public/objects/{id}
├── templates/         # Jinja2 templates (admin/* + share/*)
└── static/            # admin.css, admin.js
```

## Auth boundaries

| Path          | Auth                              |
|---------------|-----------------------------------|
| `/admin/*`    | HTTP Basic Auth                   |
| `/api/v1/*`   | API token (`Authorization: Bearer`) |
| `/share/*`    | Share-link token (+ password for private) |
| `/files/*`    | HMAC-signed, time-limited URL     |
| `/public/*`   | Public objects only               |

## Run locally (no MinIO needed)

```bash
cd metora-file
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # STORAGE_BACKEND=local by default

# Start a MongoDB (any instance works):
docker run -d -p 27017:27017 --name metora-mongo mongo:7

uvicorn app.main:app --reload
```

Open <http://localhost:8000/admin> (default Basic-Auth `admin` / `admin123`).

## Using MinIO

Set in `.env`:

```env
STORAGE_BACKEND=minio
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_DEFAULT_BUCKET=metora-file
```

```bash
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

## Presigned direct upload (`/api/v1`)

Clients (e.g. the metora backend) upload bytes **straight to storage** without
proxying through this service — a two-phase flow:

```
# 1. init-upload: pre-creates a PENDING object, returns presigned PUT instructions
POST /api/v1/buckets/{bucket}/objects/init-upload
     {"filename": "hello.txt", "content_type": "text/plain"}
  -> {"object_id": "...", "storage_key": "...",
      "upload": {"url": "...", "method": "PUT", "headers": {...}, "expires_seconds": 300}}

# 2. PUT the bytes to upload.url  (MinIO presigned PUT, or the signed local /files endpoint)
PUT <upload.url>   --data-binary @hello.txt

# 3. confirm-upload: verifies the body, backfills size/etag, flips object to ACTIVE
POST /api/v1/objects/{object_id}/confirm-upload   {}
  -> ObjectView (status="active")

# Download later:
POST /api/v1/objects/{object_id}/signed-url   (form: expires_seconds)  -> {"url": ...}
```

The legacy single-shot server-side upload (`POST /api/v1/buckets/{bucket}/objects`,
multipart) is still available and used by the Admin UI.

## Folders (virtual prefixes under a bucket)

Objects can be organised into **folders** under a bucket. A folder is a virtual,
bucket-relative path prefix (e.g. `images/2024`) — it is normalised (segments
sanitised, `.`/`..` stripped, no leading/trailing slashes) and prefixed onto the
object's storage key, so the **storage path and the signed download URL both
reflect the folder**:

```
folder="images/2024" + filename="cat.png"
  -> storage_key = "{bucket}/images/2024/{uuid}/cat.png"
  -> download URL = .../files/{bucket}/images/2024/...
```

Pass `folder` wherever you upload:

```
# Presigned direct upload
POST /api/v1/buckets/{bucket}/objects/init-upload
     {"filename": "cat.png", "folder": "images/2024"}

# Single-shot multipart upload (form field)
POST /api/v1/buckets/{bucket}/objects        (form: file=..., folder=images/2024)
```

List/browse by folder (exact match; omit to list everything):

```
GET /api/v1/objects?bucket_name={bucket}&folder=images/2024
```

The Admin UI bucket page shows sub-folders and a breadcrumb trail. **Creating a
folder and uploading a file are separate actions**, each opened from its own
button as a modal dialog (nothing is shown until you click):

- **New Folder** — `POST /admin/buckets/{bucket}/folders` (form: `name`, `parent`).
  Folders are virtual prefixes, so to let an **empty** folder persist we insert a
  lightweight placeholder marker (no bytes) carrying the folder path. Markers are
  hidden from every file listing; the folder simply "exists" until you upload into
  it. Creating a folder is idempotent.
- **Upload File** — uploads straight into the current folder (folder pre-filled).

A folder also "exists" implicitly once it contains at least one real object.

## Tests

```bash
pytest        # storage / token / signing unit tests (no DB required)
```

## Acceptance checklist

1. Create a bucket, upload a file from the bucket detail page.
2. Browse all files under **Objects**, open a file detail page.
3. Generate a signed URL from the detail page (the local backend serves it).
4. Create public and private share links from the detail page.
5. Visit a public `/share/{token}` — see file info + access buttons.
6. Visit a private `/share/{token}` — password prompt, then access after verify.
7. Create an API token (shown once), confirm the list shows only the prefix, revoke it.
