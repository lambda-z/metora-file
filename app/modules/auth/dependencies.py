from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from app.models import ApiToken
from app.modules.auth import service


async def require_api_token(
    authorization: str | None = Header(default=None),
) -> ApiToken:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raw_token = authorization.split(" ", 1)[1].strip()
    token = await service.resolve_token(raw_token)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await service.touch_last_used(token)
    return token


def require_scope(scope: str):
    """Dependency factory enforcing that the API token holds ``scope``.

    An empty ``scopes`` list is treated as full access (admin-issued token).
    """

    async def _checker(token: ApiToken = Depends(require_api_token)) -> ApiToken:
        if token.scopes and scope not in token.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token missing required scope: {scope}",
            )
        return token

    return _checker


def ensure_bucket_allowed(token: ApiToken, bucket_name: str) -> None:
    if token.allowed_buckets and bucket_name not in token.allowed_buckets:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Token not allowed for bucket: {bucket_name}",
        )
