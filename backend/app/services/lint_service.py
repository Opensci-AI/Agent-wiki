import re
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.page import Page

WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')


async def run_lint(db: AsyncSession, project_id: uuid.UUID) -> list[dict]:
    result = await db.execute(select(Page).where(Page.project_id == project_id))
    pages = list(result.scalars().all())

    title_set = {p.title.lower() for p in pages}
    issues: list[dict] = []

    incoming: set[str] = set()

    for p in pages:
        # Empty page check
        if not p.content or not p.content.strip():
            issues.append({
                "type": "empty_page",
                "page": p.path,
                "message": f"Page '{p.title}' has no content",
            })

        # Missing title check
        if not p.title or not p.title.strip():
            issues.append({
                "type": "missing_title",
                "page": p.path,
                "message": "Page has no title",
            })

        # Check wikilinks
        links = WIKILINK_RE.findall(p.content or "")
        for link in links:
            if link.lower() not in title_set:
                issues.append({
                    "type": "broken_wikilink",
                    "page": p.path,
                    "message": f"Broken wikilink to [[{link}]]",
                })
            else:
                incoming.add(link.lower())

    # Orphan pages (no incoming links from other pages)
    for p in pages:
        if p.title.lower() not in incoming:
            issues.append({
                "type": "orphan_page",
                "page": p.path,
                "message": f"Page '{p.title}' has no incoming links",
            })

    return issues
