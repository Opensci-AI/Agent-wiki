import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.project import Project
from app.services.graph_service import build_graph, get_insights
from app.api.deps import require_project_owner

router = APIRouter(prefix="/api/v1/projects/{project_id}/graph", tags=["graph"])


@router.get("")
async def graph(
    project_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    return await build_graph(db, project.id)


@router.get("/insights")
async def graph_insights(
    project_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    return await get_insights(db, project.id)
