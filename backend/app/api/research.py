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
from app.core.background import create_task, dispatch_background
from app.services.config_service import get_effective_config
from app.services.research_service import run_research
from app.api.deps import get_current_user, require_project_owner

router = APIRouter(tags=["research"])


class ResearchRequest(BaseModel):
    topic: str
    search_queries: list[str]


@router.post(
    "/api/v1/projects/{project_id}/research",
    response_model=TaskResponse,
    status_code=202,
)
async def start_research(
    body: ResearchRequest,
    project: Project = Depends(require_project_owner),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    config = await get_effective_config(db, user.id)
    llm_config = config.get("llm_config")
    if not llm_config:
        raise HTTPException(status_code=400, detail="LLM not configured")

    search_config = config.get("search_config", {})
    search_api_key = search_config.get("apiKey", "")
    if not search_api_key:
        raise HTTPException(status_code=400, detail="Search API key not configured")

    task = await create_task(
        db,
        project.id,
        user.id,
        "research",
        {"topic": body.topic, "search_queries": body.search_queries},
    )
    dispatch_background(
        task.id,
        run_research(
            task.id,
            project.id,
            body.topic,
            body.search_queries,
            llm_config,
            search_api_key,
        ),
    )
    return task


@router.get(
    "/api/v1/projects/{project_id}/research/{task_id}",
    response_model=TaskResponse,
)
async def get_research_status(
    task_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BackgroundTask).where(
            BackgroundTask.id == task_id,
            BackgroundTask.project_id == project.id,
            BackgroundTask.type == "research",
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
