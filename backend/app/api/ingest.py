import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.session import get_db
from app.models.user import User
from app.models.project import Project
from app.models.task import BackgroundTask
from app.schemas.task import TaskResponse
from app.core.background import create_task, dispatch_background, cancel_task
from app.services.config_service import get_effective_config
from app.services.ingest_service import run_ingest
from app.api.deps import get_current_user, require_project_owner

router = APIRouter(tags=["ingest"])


class IngestRequest(BaseModel):
    source_id: uuid.UUID


@router.post(
    "/api/v1/projects/{project_id}/ingest",
    response_model=TaskResponse,
    status_code=202,
)
async def start_ingest(
    body: IngestRequest,
    project: Project = Depends(require_project_owner),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    config = await get_effective_config(db, user.id)
    llm_config = config.get("llm_config")
    if not llm_config:
        raise HTTPException(status_code=400, detail="LLM not configured")

    task = await create_task(
        db, project.id, user.id, "ingest", {"source_id": str(body.source_id)}
    )
    dispatch_background(
        task.id,
        run_ingest(task.id, project.id, body.source_id, user.id, llm_config),
    )
    return task


@router.get(
    "/api/v1/projects/{project_id}/ingest/{task_id}",
    response_model=TaskResponse,
)
async def get_ingest_status(
    task_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BackgroundTask).where(
            BackgroundTask.id == task_id,
            BackgroundTask.project_id == project.id,
            BackgroundTask.type == "ingest",
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get(
    "/api/v1/projects/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
)
async def get_task_status(
    task_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """Get status of any task (extraction, ingest, etc.)"""
    result = await db.execute(
        select(BackgroundTask).where(
            BackgroundTask.id == task_id,
            BackgroundTask.project_id == project.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post(
    "/api/v1/projects/{project_id}/ingest/{task_id}/cancel",
    status_code=200,
)
async def cancel_ingest(
    task_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BackgroundTask).where(
            BackgroundTask.id == task_id,
            BackgroundTask.project_id == project.id,
            BackgroundTask.type == "ingest",
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    cancelled = cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="Task not running or already finished")
    return {"status": "cancelled"}
