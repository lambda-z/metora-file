from __future__ import annotations

from beanie import PydanticObjectId

from app.models import ObjectRelation


async def create_relation(
    *,
    object_id: str,
    relation_type: str,
    target_type: str | None = None,
    target_id: str | None = None,
    note: str | None = None,
    created_by: str | None = None,
) -> ObjectRelation:
    relation = ObjectRelation(
        object_id=PydanticObjectId(object_id),
        relation_type=relation_type,
        target_type=target_type,
        target_id=target_id,
        note=note,
        created_by=created_by,
    )
    await relation.insert()
    return relation


async def list_for_object(object_id: str) -> list[ObjectRelation]:
    return (
        await ObjectRelation.find(ObjectRelation.object_id == PydanticObjectId(object_id))
        .sort("-created_at")
        .to_list()
    )
