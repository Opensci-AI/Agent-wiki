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

def _normalize_for_match(s: str) -> str:
    """Normalize string for fuzzy matching: lowercase, remove special chars."""
    import re
    # Remove hash suffix (8 hex chars before extension)
    s = re.sub(r'-[a-f0-9]{8}\.', '.', s)
    return re.sub(r'[^a-z0-9]', '', s.lower())


async def find_related_pages(db: AsyncSession, project_id: uuid.UUID, source_name: str) -> list[Page]:
    """Find pages created from a specific source file.

    Uses fuzzy matching to handle differences between original_name and filename.
    Also matches pages from the same file uploaded multiple times (different hashes).
    """
    all_pages = await db.execute(select(Page).where(Page.project_id == project_id))
    pages = all_pages.scalars().all()
    related = []

    # Normalize source name for matching (remove special chars, lowercase)
    source_normalized = _normalize_for_match(source_name)
    # Also try matching just the base name without extension (first 30 chars should be enough)
    source_base = source_normalized[:30] if len(source_normalized) > 30 else source_normalized

    for p in pages:
        sources = p.frontmatter.get("sources", [])
        if isinstance(sources, list):
            for s in sources:
                s_normalized = _normalize_for_match(str(s))
                s_base = s_normalized[:30] if len(s_normalized) > 30 else s_normalized
                # Match if base names are similar (handles different hashes)
                if source_base == s_base or source_base in s_normalized or s_base in source_normalized:
                    related.append(p)
                    break
        elif isinstance(sources, str):
            s_normalized = _normalize_for_match(sources)
            s_base = s_normalized[:30] if len(s_normalized) > 30 else s_normalized
            if source_base == s_base or source_base in s_normalized or s_base in source_normalized:
                related.append(p)

    return related


async def search_pages_for_rag(
    db: AsyncSession, project_id: uuid.UUID, query: str, limit: int = 5
) -> list[Page]:
    """Enhanced keyword search for RAG context retrieval.

    Searches page titles and content for query keywords.
    Also includes related pages based on relationship graph.
    Returns top N pages sorted by relevance score.
    """
    if not query.strip():
        return []

    result = await db.execute(select(Page).where(Page.project_id == project_id))
    pages = list(result.scalars().all())

    # Build title lookup for relationship expansion
    title_to_page: dict[str, Page] = {}
    for p in pages:
        title_to_page[p.title.lower()] = p

    # Simple keyword matching with scoring
    query_lower = query.lower()
    keywords = [w.strip() for w in query_lower.split() if len(w.strip()) > 2]

    if not keywords:
        return []

    scored: dict[str, tuple[Page, int]] = {}  # page_id -> (page, score)

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
            scored[str(page.id)] = (page, score)

            # Add related pages with reduced score
            relationships = page.frontmatter.get("relationships", [])
            for rel in relationships:
                target_title = rel.get("target", "").lower()
                rel_type = rel.get("type", "related_to")
                target_page = title_to_page.get(target_title)
                if target_page:
                    target_id = str(target_page.id)
                    # Related pages get bonus based on relationship type
                    rel_score = 3 if rel_type in ("uses", "part_of", "implements") else 2
                    if target_id in scored:
                        existing_page, existing_score = scored[target_id]
                        scored[target_id] = (existing_page, existing_score + rel_score)
                    else:
                        scored[target_id] = (target_page, rel_score)

    # Sort by score descending
    sorted_pages = sorted(scored.values(), key=lambda x: x[1], reverse=True)

    return [p for p, _ in sorted_pages[:limit]]
