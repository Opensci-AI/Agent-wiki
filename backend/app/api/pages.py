import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.project import Project
from app.schemas.page import PageCreate, PageUpdate, PageResponse, PageListResponse
from app.services.page_service import create_page, list_pages, get_page, get_page_by_path, update_page, delete_page, find_related_pages
from app.api.deps import require_project_owner

router = APIRouter(prefix="/api/v1/projects/{project_id}/pages", tags=["pages"])

@router.post("", response_model=PageResponse, status_code=201)
async def create(project_id: uuid.UUID, req: PageCreate, project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    return await create_page(db, project.id, req.path, req.type, req.title, req.content, req.frontmatter)

@router.get("", response_model=list[PageListResponse])
async def list_all(project_id: uuid.UUID, project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db),
                   type: str | None = None, offset: int = 0, limit: int = 50):
    return await list_pages(db, project.id, type, offset, limit)

@router.get("/by-path", response_model=PageResponse)
async def by_path(project_id: uuid.UUID, path: str = Query(...), project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    return await get_page_by_path(db, project.id, path)

@router.get("/related", response_model=list[PageListResponse])
async def related(project_id: uuid.UUID, source: str = Query(...), project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    return await find_related_pages(db, project.id, source)

@router.get("/{page_id}", response_model=PageResponse)
async def get(project_id: uuid.UUID, page_id: uuid.UUID, project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    return await get_page(db, project.id, page_id)

@router.put("/{page_id}", response_model=PageResponse)
async def update(project_id: uuid.UUID, page_id: uuid.UUID, req: PageUpdate, project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    page = await get_page(db, project.id, page_id)
    return await update_page(db, page, req.title, req.content, req.frontmatter)

@router.delete("/{page_id}", status_code=204)
async def delete(project_id: uuid.UUID, page_id: uuid.UUID, project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    page = await get_page(db, project.id, page_id)
    await delete_page(db, page)
