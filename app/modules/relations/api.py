from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models import ApiToken, ObjectRelation
from app.modules.auth.dependencies import require_scope
from app.modules.relations import service

router = APIRouter()


class CreateRelationRequest(BaseModel):
    object_id: str
    relation_type: str
    target_type: str | None = None
    target_id: str | None = None
    note: str | None = None


class RelationView(BaseModel):
    id: str
    object_id: str
    relation_type: str
    target_type: str | None
    target_id: str | None
    note: str | None

    @classmethod
    def of(cls, relation: ObjectRelation) -> "RelationView":
        return cls(
            id=str(relation.id),
            object_id=str(relation.object_id),
            relation_type=relation.relation_type,
            target_type=relation.target_type,
            target_id=relation.target_id,
            note=relation.note,
        )


@router.post("", response_model=RelationView, status_code=201)
async def create_relation(
    body: CreateRelationRequest,
    token: ApiToken = Depends(require_scope("relations:write")),
):
    relation = await service.create_relation(
        object_id=body.object_id,
        relation_type=body.relation_type,
        target_type=body.target_type,
        target_id=body.target_id,
        note=body.note,
        created_by=f"token:{token.token_prefix}",
    )
    return RelationView.of(relation)


@router.get("", response_model=list[RelationView])
async def list_relations(
    object_id: str,
    _: ApiToken = Depends(require_scope("relations:read")),
):
    relations = await service.list_for_object(object_id)
    return [RelationView.of(r) for r in relations]
