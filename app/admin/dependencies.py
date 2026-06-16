from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings

_basic = HTTPBasic(auto_error=False)


def require_admin(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> str:
    """Basic-Auth guard for all ``/admin/*`` routes.

    Returns the authenticated admin username. Honours ``ADMIN_UI_ENABLED``.
    """
    if not settings.admin_ui_enabled:
        raise HTTPException(status_code=404, detail="Admin UI is disabled")

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )
    if credentials is None:
        raise unauthorized

    user_ok = secrets.compare_digest(
        credentials.username, settings.admin_ui_basic_auth_username
    )
    pass_ok = secrets.compare_digest(
        credentials.password, settings.admin_ui_basic_auth_password
    )
    if not (user_ok and pass_ok):
        raise unauthorized
    return credentials.username
