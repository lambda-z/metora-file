from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models import ApiToken
from app.models.enums import ApiTokenStatus
from app.modules.auth import security


@dataclass
class CreatedToken:
    token: ApiToken
    raw_token: str


async def create_token(
    *,
    name: str,
    owner_type: str = "system",
    owner_id: str | None = None,
    scopes: list[str] | None = None,
    allowed_buckets: list[str] | None = None,
    env: str = "live",
    created_by: str | None = None,
) -> CreatedToken:
    raw_token = security.generate_api_token(env=env)
    token = ApiToken(
        name=name,
        token_prefix=security.token_prefix(raw_token),
        token_hash=security.hash_token(raw_token),
        owner_type=owner_type,
        owner_id=owner_id,
        scopes=scopes or [],
        allowed_buckets=allowed_buckets or [],
        status=ApiTokenStatus.ACTIVE,
        created_by=created_by,
    )
    await token.insert()
    return CreatedToken(token=token, raw_token=raw_token)


async def resolve_token(raw_token: str) -> ApiToken | None:
    """Return the ACTIVE token matching the presented raw value, else None."""
    if not raw_token:
        return None
    token = await ApiToken.find_one(ApiToken.token_hash == security.hash_token(raw_token))
    if token is None or token.status != ApiTokenStatus.ACTIVE:
        return None
    return token


async def touch_last_used(token: ApiToken) -> None:
    token.last_used_at = datetime.now(timezone.utc)
    await token.save()


async def revoke_token(token_id: str) -> ApiToken | None:
    token = await ApiToken.get(token_id)
    if token is None:
        return None
    token.status = ApiTokenStatus.REVOKED
    token.revoked_at = datetime.now(timezone.utc)
    await token.save()
    return token


async def list_tokens() -> list[ApiToken]:
    return await ApiToken.find_all().sort("-created_at").to_list()
