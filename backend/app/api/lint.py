import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.project import Project
from app.services.lint_service import run_lint
from app.api.deps import require_project_owner

router = APIRouter(prefix="/api/v1/projects/{project_id}/lint", tags=["lint"])


@router.get("")
async def lint(
    project_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    issues = await run_lint(db, project.id)
    return {"issues": issues}
