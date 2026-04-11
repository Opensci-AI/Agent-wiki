import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from app.services.project_service import create_project, list_projects, update_project, soft_delete_project
from app.api.deps import get_current_user, require_project_owner

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

@router.post("", response_model=ProjectResponse, status_code=201)
async def create(req: ProjectCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await create_project(db, user.id, req.name)
    return project

@router.get("", response_model=list[ProjectListResponse])
async def list_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await list_projects(db, user.id)

@router.get("/{project_id}", response_model=ProjectResponse)
async def get(project: Project = Depends(require_project_owner)):
    return project

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update(req: ProjectUpdate, project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    return await update_project(db, project, req.name, req.purpose, req.schema_text)

@router.delete("/{project_id}", status_code=204)
async def delete(project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    await soft_delete_project(db, project)
