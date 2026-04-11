import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project

async def create_project(db: AsyncSession, owner_id: uuid.UUID, name: str, purpose: str = "", schema_text: str = "") -> Project:
    project = Project(
        id=uuid.uuid4(),
        owner_id=owner_id,
        name=name,
        purpose=purpose,
        schema_text=schema_text,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project

async def list_projects(db: AsyncSession, owner_id: uuid.UUID) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.owner_id == owner_id, Project.deleted_at.is_(None)).order_by(Project.updated_at.desc())
    )
    return list(result.scalars().all())

async def update_project(db: AsyncSession, project: Project, name: str | None, purpose: str | None, schema_text: str | None) -> Project:
    if name is not None:
        project.name = name
    if purpose is not None:
        project.purpose = purpose
    if schema_text is not None:
        project.schema_text = schema_text
    await db.commit()
    await db.refresh(project)
    return project

async def soft_delete_project(db: AsyncSession, project: Project) -> None:
    project.deleted_at = datetime.now(timezone.utc)
    await db.commit()
