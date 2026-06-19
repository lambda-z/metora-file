from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.templating import Jinja2Templates
from starlette.responses import Response

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _asset_version() -> str:
    """Cache-busting token derived from static asset mtimes.

    Bumps automatically whenever ``admin.css``/``admin.js`` change, so browsers
    never serve a stale bundle (which would, e.g., break the modal handlers).
    """
    latest = 0.0
    for rel in ("css/admin.css", "js/admin.js"):
        path = STATIC_DIR / rel
        if path.exists():
            latest = max(latest, path.stat().st_mtime)
    return str(int(latest))


# Exposed as a callable so it re-reads on every render (dev-friendly).
templates.env.globals["asset_version"] = _asset_version


def template_response(name: str, context: dict[str, Any], **kwargs: Any) -> Response:
    """Render a template using the modern Starlette ``(request, name, context)``
    signature while keeping call sites in the form ``(name, context)``.

    ``context`` must contain the ``request`` key.
    """
    request = context["request"]
    return templates.TemplateResponse(request, name, context, **kwargs)
