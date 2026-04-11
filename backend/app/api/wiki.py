# backend/app/api/wiki.py
"""Wiki API endpoints for index.md, log.md, and export."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.api.deps import require_project_owner
from app.schemas.wiki import IndexResponse, LogResponse, OperationLogResponse
from app.services.wiki_service import generate_index_md, generate_log_md
from app.services.log_service import list_operation_logs
from app.services.export_service import export_obsidian_vault


router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["wiki"])


@router.get("/wiki/index", response_model=IndexResponse)
async def get_wiki_index(
    project_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """Get generated index.md content."""
    content, page_count = await generate_index_md(db, project_id)
    return IndexResponse(
        content=content,
        page_count=page_count,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/wiki/log", response_model=LogResponse)
async def get_wiki_log(
    project_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """Get generated log.md content."""
    content, entry_count = await generate_log_md(db, project_id, limit=limit)
    return LogResponse(
        content=content,
        entry_count=entry_count,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/logs", response_model=list[OperationLogResponse])
async def get_operation_logs(
    project_id: uuid.UUID,
    operation: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """List operation logs as JSON."""
    logs = await list_operation_logs(
        db, project_id, operation=operation, limit=limit, offset=offset
    )
    return [
        OperationLogResponse(
            id=str(log.id),
            project_id=str(log.project_id),
            user_id=str(log.user_id) if log.user_id else None,
            operation=log.operation,
            title=log.title,
            details=log.details or {},
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/export")
async def export_vault(
    project_id: uuid.UUID,
    include_raw: bool = Query(False),
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """Export project as Obsidian vault ZIP."""
    # Get user_id from project owner check
    user_id = project.owner_id

    zip_bytes, filename = await export_obsidian_vault(
        db, project_id, user_id=user_id, include_raw=include_raw
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
