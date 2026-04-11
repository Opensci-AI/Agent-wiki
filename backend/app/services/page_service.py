import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.page import Page

async def create_page(db: AsyncSession, project_id: uuid.UUID, path: str, type: str, title: str, content: str = "", frontmatter: dict = {}) -> Page:
    existing = await db.execute(select(Page).where(Page.project_id == project_id, Page.path == path))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Page path already exists")
    page = Page(id=uuid.uuid4(), project_id=project_id, path=path, type=type, title=title, content=content, frontmatter=frontmatter)
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page

async def list_pages(db: AsyncSession, project_id: uuid.UUID, type: str | None = None, offset: int = 0, limit: int = 50) -> list[Page]:
    q = select(Page).where(Page.project_id == project_id)
    if type:
        q = q.where(Page.type == type)
    q = q.order_by(Page.path).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())

async def get_page(db: AsyncSession, project_id: uuid.UUID, page_id: uuid.UUID) -> Page:
    result = await db.execute(select(Page).where(Page.id == page_id, Page.project_id == project_id))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

async def get_page_by_path(db: AsyncSession, project_id: uuid.UUID, path: str) -> Page:
    result = await db.execute(select(Page).where(Page.project_id == project_id, Page.path == path))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

async def update_page(db: AsyncSession, page: Page, title: str | None, content: str | None, frontmatter: dict | None) -> Page:
    if title is not None:
        page.title = title
    if content is not None:
        page.content = content
    if frontmatter is not None:
        page.frontmatter = frontmatter
    await db.commit()
    await db.refresh(page)
    return page

async def delete_page(db: AsyncSession, page: Page) -> None:
    await db.delete(page)
    await db.commit()

async def find_related_pages(db: AsyncSession, project_id: uuid.UUID, source_name: str) -> list[Page]:
    all_pages = await db.execute(select(Page).where(Page.project_id == project_id))
    pages = all_pages.scalars().all()
    related = []
    source_lower = source_name.lower()
    for p in pages:
        sources = p.frontmatter.get("sources", [])
        if isinstance(sources, list):
            if any(source_lower in str(s).lower() for s in sources):
                related.append(p)
        elif isinstance(sources, str) and source_lower in sources.lower():
            related.append(p)
    return related


async def search_pages_for_rag(
    db: AsyncSession, project_id: uuid.UUID, query: str, limit: int = 5
) -> list[Page]:
    """Simple keyword search for RAG context retrieval.

    Searches page titles and content for query keywords.
    Returns top N pages sorted by relevance score.
    """
    if not query.strip():
        return []

    result = await db.execute(select(Page).where(Page.project_id == project_id))
    pages = list(result.scalars().all())

    # Simple keyword matching with scoring
    query_lower = query.lower()
    keywords = [w.strip() for w in query_lower.split() if len(w.strip()) > 2]

    if not keywords:
        return []

    scored: list[tuple[Page, int]] = []
    for page in pages:
        score = 0
        title_lower = (page.title or "").lower()
        content_lower = (page.content or "").lower()

        for kw in keywords:
            # Title matches are worth more
            if kw in title_lower:
                score += 10
            # Content matches
            score += content_lower.count(kw)

        if score > 0:
            scored.append((page, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    return [p for p, _ in scored[:limit]]
