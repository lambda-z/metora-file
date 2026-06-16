from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.templating import Jinja2Templates
from starlette.responses import Response

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def template_response(name: str, context: dict[str, Any], **kwargs: Any) -> Response:
    """Render a template using the modern Starlette ``(request, name, context)``
    signature while keeping call sites in the form ``(name, context)``.

    ``context`` must contain the ``request`` key.
    """
    request = context["request"]
    return templates.TemplateResponse(request, name, context, **kwargs)
