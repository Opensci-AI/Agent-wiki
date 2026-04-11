import uuid
import re
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.source import Source
from app.core.storage import get_storage

ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx", "xlsx", "xls", "ods", "txt", "md", "csv", "png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 50 * 1024 * 1024


def _detect_content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext if ext in ALLOWED_EXTENSIONS else "unknown"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:50]


async def upload_source(db: AsyncSession, project_id: uuid.UUID, filename: str, data: bytes) -> Source:
    content_type = _detect_content_type(filename)
    if content_type == "unknown":
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {filename}")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    unique_name = f"{_slugify(base)}-{uuid.uuid4().hex[:8]}.{ext}"

    storage = get_storage()
    storage_path = f"{project_id}/{unique_name}"
    await storage.save(storage_path, data)

    text_types = {"txt", "md", "csv"}
    status = "ready" if content_type in text_types else "uploaded"
    extracted = data.decode("utf-8", errors="replace") if content_type in text_types else None

    source = Source(
        id=uuid.uuid4(), project_id=project_id, filename=unique_name,
        original_name=filename, content_type=content_type,
        extracted_text=extracted, file_size=len(data),
        storage_path=storage_path, status=status,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


async def create_clip(db: AsyncSession, project_id: uuid.UUID, title: str, url: str, content: str) -> Source:
    slug = _slugify(title)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{slug}-{date_str}.md"

    md_content = f"""---
type: clip
title: "{title}"
url: "{url}"
clipped: {date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}
origin: web-clip
sources: []
tags: [web-clip]
---

# {title}

Source: {url}

{content}
"""
    storage = get_storage()
    storage_path = f"{project_id}/{filename}"
    data = md_content.encode("utf-8")
    await storage.save(storage_path, data)

    source = Source(
        id=uuid.uuid4(), project_id=project_id, filename=filename,
        original_name=title, content_type="clip",
        extracted_text=md_content, file_size=len(data),
        storage_path=storage_path, status="ready",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


async def list_sources(db: AsyncSession, project_id: uuid.UUID, status: str | None = None, offset: int = 0, limit: int = 50) -> list[Source]:
    q = select(Source).where(Source.project_id == project_id)
    if status:
        q = q.where(Source.status == status)
    q = q.order_by(Source.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_source(db: AsyncSession, project_id: uuid.UUID, source_id: uuid.UUID) -> Source:
    result = await db.execute(select(Source).where(Source.id == source_id, Source.project_id == project_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


async def delete_source(db: AsyncSession, source: Source) -> None:
    storage = get_storage()
    await storage.delete(source.storage_path)
    await db.delete(source)
    await db.commit()
