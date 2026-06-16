from __future__ import annotations

from app.models import AuditLog


async def record(
    *,
    action: str,
    actor_type: str | None = None,
    actor_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        detail=detail or {},
    )
    await log.insert()
    return log


async def recent(limit: int = 10) -> list[AuditLog]:
    return await AuditLog.find_all().sort("-created_at").limit(limit).to_list()
