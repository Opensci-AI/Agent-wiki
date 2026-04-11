"""Obsidian vault export service."""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page
from app.models.project import Project
from app.services.page_service import list_pages
from app.services.source_service import list_sources
from app.services.wiki_service import generate_index_md, generate_log_md
from app.services.log_service import append_operation_log
from app.core.storage import get_storage


def render_page_with_frontmatter(page: Page) -> str:
    """Render page content with YAML frontmatter."""
    frontmatter: dict = {
        "title": page.title,
        "type": page.type,
        "path": page.path,
    }

    # Merge existing frontmatter
    if page.frontmatter:
        frontmatter.update(page.frontmatter)

    # Add timestamps
    if page.created_at:
        frontmatter["created"] = page.created_at.isoformat()
    if page.updated_at:
        frontmatter["updated"] = page.updated_at.isoformat()

    yaml_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False
    )

    return f"---\n{yaml_str}---\n\n{page.content}"


def _slugify(name: str) -> str:
    """Convert project name to safe directory name."""
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower()).strip("-")


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    """Get project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project {project_id} not found")
    return project


async def export_obsidian_vault(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    include_raw: bool = False,
) -> tuple[bytes, str]:
    """Export project as Obsidian vault ZIP.

    Returns: (zip_bytes, filename)
    """
    project = await _get_project(db, project_id)
    pages = await list_pages(db, project_id)

    dir_name = _slugify(project.name) or "wiki"
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{dir_name}-{date_str}.zip"

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # .obsidian/app.json (minimal config)
        zf.writestr(f"{dir_name}/.obsidian/app.json", "{}")

        # schema.md
        if project.schema_text:
            zf.writestr(f"{dir_name}/schema.md", project.schema_text)

        # purpose.md
        if project.purpose:
            purpose_content = f"# Purpose\n\n{project.purpose}"
            zf.writestr(f"{dir_name}/purpose.md", purpose_content)

        # wiki/index.md
        index_content, _ = await generate_index_md(db, project_id)
        zf.writestr(f"{dir_name}/wiki/index.md", index_content)

        # wiki/log.md
        log_content, _ = await generate_log_md(db, project_id)
        zf.writestr(f"{dir_name}/wiki/log.md", log_content)

        # Wiki pages with YAML frontmatter
        for page in pages:
            content = render_page_with_frontmatter(page)
            zf.writestr(f"{dir_name}/{page.path}", content)

        # Raw sources (optional)
        if include_raw:
            sources = await list_sources(db, project_id)
            storage = get_storage()
            for source in sources:
                try:
                    data = await storage.read(source.storage_path)
                    zf.writestr(f"{dir_name}/raw/{source.original_name}", data)
                except (FileNotFoundError, OSError):
                    # Skip missing files
                    pass

    buffer.seek(0)
    zip_bytes = buffer.read()

    # Log export operation
    await append_operation_log(
        db,
        project_id=project_id,
        user_id=user_id,
        operation="export",
        title=filename,
        details={
            "page_count": len(pages),
            "include_raw": include_raw,
            "size_bytes": len(zip_bytes),
        }
    )

    return zip_bytes, filename
