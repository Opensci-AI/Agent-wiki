import uuid
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.page import Page


async def search_pages(db: AsyncSession, project_id: uuid.UUID, query: str, limit: int = 20) -> list[Page]:
    pattern = f"%{query}%"
    result = await db.execute(
        select(Page)
        .where(
            Page.project_id == project_id,
            or_(
                Page.title.ilike(pattern),
                Page.content.ilike(pattern),
            ),
        )
        .order_by(Page.title)
        .limit(limit)
    )
    return list(result.scalars().all())
