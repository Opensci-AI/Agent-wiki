"""Operation logging service."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operation_log import OperationLog


async def append_operation_log(
    db: AsyncSession,
    project_id: uuid.UUID,
    operation: str,
    title: str = "",
    details: dict[str, Any] | None = None,
    user_id: uuid.UUID | None = None,
) -> OperationLog:
    """Append entry to operation_logs table."""
    log = OperationLog(
        project_id=project_id,
        user_id=user_id,
        operation=operation,
        title=title or None,
        details=details or {},
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_operation_logs(
    db: AsyncSession,
    project_id: uuid.UUID,
    operation: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[OperationLog]:
    """List operation logs for a project."""
    query = select(OperationLog).where(OperationLog.project_id == project_id)

    if operation:
        query = query.where(OperationLog.operation == operation)

    query = query.order_by(OperationLog.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())
