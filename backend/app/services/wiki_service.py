# backend/app/services/wiki_service.py
"""Wiki generation services for index.md and log.md."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page
from app.models.operation_log import OperationLog


# Simple in-memory cache (replace with Redis for production)
_index_cache: dict[str, tuple[str, int, datetime]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


async def generate_index_md(db: AsyncSession, project_id: uuid.UUID) -> tuple[str, int]:
    """Generate index.md content from pages table.

    Returns: (content, page_count)
    """
    cache_key = f"index_md:{project_id}"

    # Check cache
    if cache_key in _index_cache:
        content, count, cached_at = _index_cache[cache_key]
        if (datetime.now(timezone.utc) - cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            return content, count

    # Query pages
    result = await db.execute(
        select(Page)
        .where(Page.project_id == project_id)
        .order_by(Page.type, Page.title)
    )
    pages = list(result.scalars().all())

    # Group by type
    grouped: dict[str, list[Page]] = {}
    for page in pages:
        grouped.setdefault(page.type, []).append(page)

    # Render markdown
    total_count = len(pages)
    lines = ["# Wiki Index\n\n"]
    lines.append(f"*{total_count} pages*\n")

    for page_type in ["entity", "concept", "query", "general"]:
        if page_type not in grouped:
            continue
        lines.append(f"\n## {page_type.title()}s\n\n")
        for page in grouped[page_type]:
            summary = page.frontmatter.get("summary", "") if page.frontmatter else ""
            source_count = len(page.frontmatter.get("sources", [])) if page.frontmatter else 0
            line = f"- [[{page.path}|{page.title}]]"
            if summary:
                line += f" — {summary}"
            if source_count:
                line += f" ({source_count} sources)"
            lines.append(line + "\n")

    content = "".join(lines)

    # Cache result
    _index_cache[cache_key] = (content, total_count, datetime.now(timezone.utc))

    return content, total_count


async def generate_log_md(
    db: AsyncSession,
    project_id: uuid.UUID,
    limit: int = 100
) -> tuple[str, int]:
    """Generate log.md content from operation_logs table.

    Returns: (content, entry_count)
    """
    result = await db.execute(
        select(OperationLog)
        .where(OperationLog.project_id == project_id)
        .order_by(OperationLog.created_at.desc())
        .limit(limit)
    )
    logs = list(result.scalars().all())

    lines = ["# Operation Log\n\n"]

    for log in logs:
        date = log.created_at.strftime("%Y-%m-%d %H:%M")
        line = f"## [{date}] {log.operation}"
        if log.title:
            line += f" | {log.title}"
        lines.append(line + "\n\n")

        # Add details based on operation type
        details = log.details or {}
        if log.operation == "ingest":
            # Show pages written count and list
            if details.get("pages_written"):
                lines.append(f"- Pages written: {details['pages_written']}\n")
            if details.get("paths"):
                lines.append(f"- Paths: {', '.join(details['paths'])}\n")
        elif log.operation == "lint":
            if "issues_found" in details:
                lines.append(f"- Issues found: {details['issues_found']}\n")
        elif log.operation == "export":
            if "page_count" in details:
                lines.append(f"- Pages exported: {details['page_count']}\n")

        lines.append("\n")

    return "".join(lines), len(logs)


def invalidate_index_cache(project_id: uuid.UUID) -> None:
    """Invalidate cached index.md for a project."""
    cache_key = f"index_md:{project_id}"
    _index_cache.pop(cache_key, None)
