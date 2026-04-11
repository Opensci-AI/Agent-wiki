import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.project import Project
from app.schemas.page import PageResponse
from app.services.search_service import search_pages
from app.api.deps import require_project_owner

router = APIRouter(prefix="/api/v1/projects/{project_id}/search", tags=["search"])


@router.get("", response_model=list[PageResponse])
async def search(
    project_id: uuid.UUID,
    q: str = Query(..., min_length=1),
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    return await search_pages(db, project.id, q)
