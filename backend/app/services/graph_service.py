import re
import uuid
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.page import Page

WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')


async def build_graph(db: AsyncSession, project_id: uuid.UUID) -> dict:
    result = await db.execute(select(Page).where(Page.project_id == project_id))
    pages = list(result.scalars().all())

    # Build lookup: title (lowercased) -> page
    title_to_page: dict[str, Page] = {}
    for p in pages:
        title_to_page[p.title.lower()] = p

    nodes = []
    edges = []
    seen_edges: set[tuple[str, str]] = set()

    for p in pages:
        nodes.append({
            "id": str(p.id),
            "title": p.title,
            "path": p.path,
            "type": p.type,
        })

        links = WIKILINK_RE.findall(p.content or "")
        for link in links:
            target = title_to_page.get(link.lower())
            if target and target.id != p.id:
                edge_key = (str(p.id), str(target.id))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": str(p.id),
                        "target": str(target.id),
                        "label": link,
                    })

    return {"nodes": nodes, "edges": edges}


async def get_insights(db: AsyncSession, project_id: uuid.UUID) -> dict:
    result = await db.execute(select(Page).where(Page.project_id == project_id))
    pages = list(result.scalars().all())

    title_to_page: dict[str, Page] = {}
    for p in pages:
        title_to_page[p.title.lower()] = p

    # Count incoming links for each page
    incoming: dict[str, int] = defaultdict(int)
    for p in pages:
        links = WIKILINK_RE.findall(p.content or "")
        for link in links:
            target = title_to_page.get(link.lower())
            if target and target.id != p.id:
                incoming[str(target.id)] += 1

    orphans = []
    hubs = []
    for p in pages:
        pid_str = str(p.id)
        count = incoming.get(pid_str, 0)
        if count == 0:
            orphans.append({"id": pid_str, "title": p.title, "path": p.path})

    # Hubs: pages with >= 2 incoming links, sorted descending
    for p in pages:
        pid_str = str(p.id)
        count = incoming.get(pid_str, 0)
        if count >= 2:
            hubs.append({"id": pid_str, "title": p.title, "path": p.path, "incoming_links": count})
    hubs.sort(key=lambda h: h["incoming_links"], reverse=True)

    return {"orphans": orphans, "hubs": hubs}
