from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.models import ApiToken
from app.modules.auth import service
from app.modules.auth.dependencies import require_scope

router = APIRouter()


class CreateTokenRequest(BaseModel):
    name: str
    owner_type: str = "system"
    owner_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    allowed_buckets: list[str] = Field(default_factory=list)


class TokenView(BaseModel):
    id: str
    name: str
    token_prefix: str
    owner_type: str
    owner_id: str | None
    scopes: list[str]
    allowed_buckets: list[str]
    status: str

    @classmethod
    def of(cls, token: ApiToken) -> "TokenView":
        return cls(
            id=str(token.id),
            name=token.name,
            token_prefix=token.token_prefix,
            owner_type=token.owner_type,
            owner_id=token.owner_id,
            scopes=token.scopes,
            allowed_buckets=token.allowed_buckets,
            status=token.status.value,
        )


class CreateTokenResponse(TokenView):
    raw_token: str


@router.get("", response_model=list[TokenView])
async def list_api_tokens(_: ApiToken = Depends(require_scope("buckets:read"))):
    tokens = await service.list_tokens()
    return [TokenView.of(t) for t in tokens]


@router.post("", response_model=CreateTokenResponse)
async def create_api_token(
    body: CreateTokenRequest,
    _: ApiToken = Depends(require_scope("buckets:write")),
):
    created = await service.create_token(
        name=body.name,
        owner_type=body.owner_type,
        owner_id=body.owner_id,
        scopes=body.scopes,
        allowed_buckets=body.allowed_buckets,
        created_by="api",
    )
    view = TokenView.of(created.token)
    return CreateTokenResponse(raw_token=created.raw_token, **view.model_dump())


@router.post("/{token_id}/revoke", response_model=TokenView)
async def revoke_api_token(
    token_id: str,
    _: ApiToken = Depends(require_scope("buckets:write")),
):
    token = await service.revoke_token(token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="API token not found")
    return TokenView.of(token)
