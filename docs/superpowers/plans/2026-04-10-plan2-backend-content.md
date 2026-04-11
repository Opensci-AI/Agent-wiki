# Plan 2: Backend Content — Pages, Sources, Storage, Extraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add wiki page CRUD, file upload/storage, web clipper endpoint, and document extraction — enabling users to manage content within projects.

**Architecture:** Extends the 3-layer backend from Plan 1. Pages stored in PostgreSQL with virtual paths. Files stored via a `StorageBackend` abstraction (LocalStorage now, S3 later). Text extraction uses Python libraries for structured formats (DOCX, XLSX, PPTX, PDF) and OpenRouter for scanned/image content. Background task model supports async extraction.

**Tech Stack:** pdfminer.six, python-docx, python-pptx, openpyxl, aiofiles, Pillow (image metadata)

**Spec:** `docs/superpowers/specs/2026-04-10-llm-wiki-web-design.md`

**Depends on:** Plan 1 (auth, projects, config) — already implemented on branch `feat/web-backend`

---

## File Structure

```
backend/app/
├── models/
│   ├── page.py                    # Page ORM (wiki pages)
│   ├── source.py                  # Source ORM (uploaded files/clips)
│   └── task.py                    # BackgroundTask ORM
│
├── schemas/
│   ├── page.py                    # Page request/response schemas
│   ├── source.py                  # Source request/response schemas
│   └── task.py                    # Task status schema
│
├── services/
│   ├── page_service.py            # Page CRUD + by-path + related lookup
│   ├── source_service.py          # Upload, clip, delete
│   └── extraction_service.py      # Format detection + text extraction
│
├── core/
│   ├── storage.py                 # StorageBackend ABC + LocalStorage
│   └── background.py              # Async task manager
│
├── api/
│   ├── pages.py                   # /projects/:id/pages/* routes
│   └── sources.py                 # /projects/:id/sources/* routes

backend/tests/
├── test_pages.py
├── test_sources.py
└── test_extraction.py
```

---

### Task 1: Page Model + Schemas + Migration

**Files:**
- Create: `backend/app/models/page.py`
- Create: `backend/app/schemas/page.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create Page model**

```python
# backend/app/models/page.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("project_id", "path", name="uq_page_project_path"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    path: Mapped[str] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(50))  # entity, concept, source, query, comparison, synthesis
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, default="")
    frontmatter: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Create Page schemas**

```python
# backend/app/schemas/page.py
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel

class PageCreate(BaseModel):
    path: str
    type: str = "entity"
    title: str
    content: str = ""
    frontmatter: dict[str, Any] = {}

class PageUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    frontmatter: dict[str, Any] | None = None

class PageResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    path: str
    type: str
    title: str
    content: str
    frontmatter: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class PageListResponse(BaseModel):
    id: uuid.UUID
    path: str
    type: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Update models __init__.py**

```python
from app.models.user import User
from app.models.project import Project
from app.models.config import SystemConfig, UserConfig
from app.models.page import Page

__all__ = ["User", "Project", "SystemConfig", "UserConfig", "Page"]
```

- [ ] **Step 4: Generate and apply migration**

```bash
cd backend && source venv/bin/activate
alembic revision --autogenerate -m "add pages table"
alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/riley/Nhat Cuong/code/00-personal/llm_wiki"
git add backend/app/models/page.py backend/app/schemas/page.py backend/app/models/__init__.py backend/alembic/
git commit -m "feat(backend): add Page model and schemas"
```

---

### Task 2: Page Service + Routes + Tests

**Files:**
- Create: `backend/app/services/page_service.py`
- Create: `backend/app/api/pages.py`
- Create: `backend/tests/test_pages.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create page service**

```python
# backend/app/services/page_service.py
import uuid
from sqlalchemy import select, func as sa_func
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
    """Find wiki pages related to a source file by checking frontmatter sources field."""
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
```

- [ ] **Step 2: Create page routes**

```python
# backend/app/api/pages.py
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
```

- [ ] **Step 3: Register router in main.py**

Add to `backend/app/main.py`:
```python
from app.api.pages import router as pages_router
app.include_router(pages_router)
```

- [ ] **Step 4: Create tests**

```python
# backend/tests/test_pages.py
async def _setup(client, email="pages@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Pages User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]

async def test_create_page(client):
    token, pid = await _setup(client)
    resp = await client.post(f"/api/v1/projects/{pid}/pages", json={
        "path": "entities/ml.md", "type": "entity", "title": "Machine Learning", "content": "# ML"
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Machine Learning"

async def test_list_pages(client):
    token, pid = await _setup(client, "list-pages@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/a.md", "type": "entity", "title": "A"}, headers=h)
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "concepts/b.md", "type": "concept", "title": "B"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/pages", headers=h)
    assert len(resp.json()) == 2
    # Filter by type
    resp2 = await client.get(f"/api/v1/projects/{pid}/pages?type=entity", headers=h)
    assert len(resp2.json()) == 1

async def test_get_page(client):
    token, pid = await _setup(client, "get-page@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/x.md", "type": "entity", "title": "X"}, headers=h)
    page_id = created.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/pages/{page_id}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["title"] == "X"

async def test_get_by_path(client):
    token, pid = await _setup(client, "bypath@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/find-me.md", "type": "entity", "title": "FindMe"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/pages/by-path?path=entities/find-me.md", headers=h)
    assert resp.status_code == 200
    assert resp.json()["title"] == "FindMe"

async def test_update_page(client):
    token, pid = await _setup(client, "update-page@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/u.md", "type": "entity", "title": "Old"}, headers=h)
    page_id = created.json()["id"]
    resp = await client.put(f"/api/v1/projects/{pid}/pages/{page_id}", json={"title": "New", "content": "updated"}, headers=h)
    assert resp.json()["title"] == "New"
    assert resp.json()["content"] == "updated"

async def test_delete_page(client):
    token, pid = await _setup(client, "del-page@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/d.md", "type": "entity", "title": "D"}, headers=h)
    page_id = created.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}/pages/{page_id}", headers=h)
    assert resp.status_code == 204
    get_resp = await client.get(f"/api/v1/projects/{pid}/pages/{page_id}", headers=h)
    assert get_resp.status_code == 404

async def test_duplicate_path(client):
    token, pid = await _setup(client, "dup-page@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/same.md", "type": "entity", "title": "First"}, headers=h)
    resp = await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/same.md", "type": "entity", "title": "Second"}, headers=h)
    assert resp.status_code == 409

async def test_find_related(client):
    token, pid = await _setup(client, "related@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={
        "path": "entities/ml.md", "type": "entity", "title": "ML",
        "frontmatter": {"sources": ["paper.pdf"]}
    }, headers=h)
    await client.post(f"/api/v1/projects/{pid}/pages", json={
        "path": "entities/dl.md", "type": "entity", "title": "DL",
        "frontmatter": {"sources": ["other.pdf"]}
    }, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/pages/related?source=paper.pdf", headers=h)
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "ML"
```

- [ ] **Step 5: Run tests**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v
```

Expected: All previous tests + 8 new page tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat(backend): add page CRUD with path lookup and related search"
```

---

### Task 3: Storage Abstraction Layer

**Files:**
- Create: `backend/app/core/storage.py`

- [ ] **Step 1: Create storage module**

```python
# backend/app/core/storage.py
import os
import aiofiles
from abc import ABC, abstractmethod
from app.config import settings

class StorageBackend(ABC):
    @abstractmethod
    async def save(self, path: str, data: bytes) -> str:
        """Save data, return storage path."""

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read file data."""

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete file."""

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists."""

class LocalStorage(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def _full_path(self, path: str) -> str:
        return os.path.join(self.base_path, path)

    async def save(self, path: str, data: bytes) -> str:
        full = self._full_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        async with aiofiles.open(full, "wb") as f:
            await f.write(data)
        return path

    async def read(self, path: str) -> bytes:
        async with aiofiles.open(self._full_path(path), "rb") as f:
            return await f.read()

    async def delete(self, path: str) -> None:
        full = self._full_path(path)
        if os.path.exists(full):
            os.remove(full)

    async def exists(self, path: str) -> bool:
        return os.path.exists(self._full_path(path))

def get_storage() -> StorageBackend:
    return LocalStorage(settings.storage_path)
```

- [ ] **Step 2: Add aiofiles to requirements.txt**

Append to `backend/requirements.txt`:
```
aiofiles==24.1.0
```

Install: `pip install aiofiles==24.1.0`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/storage.py backend/requirements.txt
git commit -m "feat(backend): add storage abstraction layer with LocalStorage"
```

---

### Task 4: Source Model + Schemas + Migration

**Files:**
- Create: `backend/app/models/source.py`
- Create: `backend/app/schemas/source.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create Source model**

```python
# backend/app/models/source.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, BigInteger, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("project_id", "filename", name="uq_source_project_filename"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(50))  # pdf, docx, txt, md, clip, pptx, xlsx
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    storage_path: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(50), default="uploaded")  # uploaded, extracting, ready, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Create Source schemas**

```python
# backend/app/schemas/source.py
import uuid
from datetime import datetime
from pydantic import BaseModel

class ClipRequest(BaseModel):
    title: str
    url: str
    content: str

class SourceResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    original_name: str
    content_type: str
    file_size: int
    status: str
    created_at: datetime
    extracted_text: str | None = None

    model_config = {"from_attributes": True}

class SourceListResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_name: str
    content_type: str
    file_size: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Update models __init__.py**

```python
from app.models.user import User
from app.models.project import Project
from app.models.config import SystemConfig, UserConfig
from app.models.page import Page
from app.models.source import Source

__all__ = ["User", "Project", "SystemConfig", "UserConfig", "Page", "Source"]
```

- [ ] **Step 4: Generate and apply migration**

```bash
cd backend && source venv/bin/activate
alembic revision --autogenerate -m "add sources table"
alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/source.py backend/app/schemas/source.py backend/app/models/__init__.py backend/alembic/
git commit -m "feat(backend): add Source model and schemas"
```

---

### Task 5: Source Service + Routes + Tests

**Files:**
- Create: `backend/app/services/source_service.py`
- Create: `backend/app/api/sources.py`
- Create: `backend/tests/test_sources.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create source service**

```python
# backend/app/services/source_service.py
import uuid
import re
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.source import Source
from app.core.storage import get_storage

ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx", "xlsx", "xls", "ods", "txt", "md", "csv", "png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

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

    # Generate unique filename
    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    unique_name = f"{_slugify(base)}-{uuid.uuid4().hex[:8]}.{ext}"

    storage = get_storage()
    storage_path = f"{project_id}/{unique_name}"
    await storage.save(storage_path, data)

    # Determine initial status
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
```

- [ ] **Step 2: Create source routes**

```python
# backend/app/api/sources.py
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.project import Project
from app.schemas.source import ClipRequest, SourceResponse, SourceListResponse
from app.services.source_service import upload_source, create_clip, list_sources, get_source, delete_source
from app.api.deps import require_project_owner

router = APIRouter(prefix="/api/v1/projects/{project_id}/sources", tags=["sources"])

@router.post("/upload", response_model=SourceResponse, status_code=201)
async def upload(project_id: uuid.UUID, file: UploadFile = File(...),
                 project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    data = await file.read()
    return await upload_source(db, project.id, file.filename or "unnamed", data)

@router.post("/clip", response_model=SourceResponse, status_code=201)
async def clip(project_id: uuid.UUID, req: ClipRequest,
               project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    return await create_clip(db, project.id, req.title, req.url, req.content)

@router.get("", response_model=list[SourceListResponse])
async def list_all(project_id: uuid.UUID, project: Project = Depends(require_project_owner),
                   db: AsyncSession = Depends(get_db), status: str | None = None, offset: int = 0, limit: int = 50):
    return await list_sources(db, project.id, status, offset, limit)

@router.get("/{source_id}", response_model=SourceResponse)
async def get(project_id: uuid.UUID, source_id: uuid.UUID,
              project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    return await get_source(db, project.id, source_id)

@router.delete("/{source_id}", status_code=204)
async def delete(project_id: uuid.UUID, source_id: uuid.UUID,
                 project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    source = await get_source(db, project.id, source_id)
    await delete_source(db, source)
```

- [ ] **Step 3: Register router in main.py**

```python
from app.api.sources import router as sources_router
app.include_router(sources_router)
```

- [ ] **Step 4: Create tests**

```python
# backend/tests/test_sources.py
import io

async def _setup(client, email="src@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Src User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]

async def test_upload_txt(client):
    token, pid = await _setup(client)
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")}, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["content_type"] == "txt"
    assert data["status"] == "ready"
    assert data["extracted_text"] == "hello world"

async def test_upload_pdf(client):
    token, pid = await _setup(client, "pdf@example.com")
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("paper.pdf", b"%PDF-fake", "application/pdf")}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["status"] == "uploaded"
    assert resp.json()["extracted_text"] is None

async def test_upload_unsupported(client):
    token, pid = await _setup(client, "bad@example.com")
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("virus.exe", b"bad", "application/octet-stream")}, headers=h)
    assert resp.status_code == 400

async def test_clip(client):
    token, pid = await _setup(client, "clip@example.com")
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/sources/clip", json={
        "title": "Interesting Article", "url": "https://example.com/article", "content": "Article body here"
    }, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["content_type"] == "clip"
    assert data["status"] == "ready"
    assert "web-clip" in data["extracted_text"]

async def test_list_sources(client):
    token, pid = await _setup(client, "listsrc@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("a.txt", b"aa", "text/plain")}, headers=h)
    await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("b.md", b"bb", "text/plain")}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/sources", headers=h)
    assert len(resp.json()) == 2

async def test_get_source(client):
    token, pid = await _setup(client, "getsrc@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("x.txt", b"xx", "text/plain")}, headers=h)
    sid = created.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/sources/{sid}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["extracted_text"] == "xx"

async def test_delete_source(client):
    token, pid = await _setup(client, "delsrc@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("del.txt", b"del", "text/plain")}, headers=h)
    sid = created.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}/sources/{sid}", headers=h)
    assert resp.status_code == 204
    get_resp = await client.get(f"/api/v1/projects/{pid}/sources/{sid}", headers=h)
    assert get_resp.status_code == 404
```

- [ ] **Step 5: Run tests**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v
```

Expected: All previous + 7 new source tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat(backend): add source upload, clip, CRUD with storage layer"
```

---

### Task 6: Background Task Model + Manager

**Files:**
- Create: `backend/app/models/task.py`
- Create: `backend/app/schemas/task.py`
- Create: `backend/app/core/background.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py` (startup recovery)

- [ ] **Step 1: Create Task model**

```python
# backend/app/models/task.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class BackgroundTask(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(50))  # ingest, deep_research, extraction
    status: Mapped[str] = mapped_column(String(50), default="queued")  # queued, running, completed, failed
    input: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Create Task schema**

```python
# backend/app/schemas/task.py
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel

class TaskResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    progress_pct: int
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create background task manager**

```python
# backend/app/core/background.py
import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session
from app.models.task import BackgroundTask

_running_tasks: dict[uuid.UUID, asyncio.Task] = {}

async def recover_orphaned_tasks():
    """On startup, mark any 'running' tasks as failed (server restarted)."""
    async with async_session() as db:
        await db.execute(
            update(BackgroundTask)
            .where(BackgroundTask.status == "running")
            .values(status="failed", error="Server restarted", completed_at=datetime.now(timezone.utc))
        )
        await db.commit()

async def create_task(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, task_type: str, input_data: dict) -> BackgroundTask:
    task = BackgroundTask(
        id=uuid.uuid4(), project_id=project_id, user_id=user_id,
        type=task_type, status="queued", input=input_data,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

async def update_task_status(task_id: uuid.UUID, status: str, progress: int = 0, result: dict | None = None, error: str | None = None):
    async with async_session() as db:
        stmt = update(BackgroundTask).where(BackgroundTask.id == task_id).values(
            status=status, progress_pct=progress, result=result, error=error, updated_at=datetime.now(timezone.utc),
        )
        if status == "running":
            stmt = stmt.values(started_at=datetime.now(timezone.utc))
        if status in ("completed", "failed"):
            stmt = stmt.values(completed_at=datetime.now(timezone.utc))
        await db.execute(stmt)
        await db.commit()

def dispatch_background(task_id: uuid.UUID, coro):
    """Run a coroutine as a background asyncio task."""
    loop_task = asyncio.create_task(coro)
    _running_tasks[task_id] = loop_task
    loop_task.add_done_callback(lambda _: _running_tasks.pop(task_id, None))

def cancel_task(task_id: uuid.UUID) -> bool:
    task = _running_tasks.get(task_id)
    if task:
        task.cancel()
        return True
    return False
```

- [ ] **Step 4: Update models __init__.py**

```python
from app.models.user import User
from app.models.project import Project
from app.models.config import SystemConfig, UserConfig
from app.models.page import Page
from app.models.source import Source
from app.models.task import BackgroundTask

__all__ = ["User", "Project", "SystemConfig", "UserConfig", "Page", "Source", "BackgroundTask"]
```

- [ ] **Step 5: Add startup recovery to main.py lifespan**

In `backend/app/main.py`, add inside the lifespan function (after admin seed, before `yield`):
```python
from app.core.background import recover_orphaned_tasks
await recover_orphaned_tasks()
```

- [ ] **Step 6: Generate migration and apply**

```bash
cd backend && alembic revision --autogenerate -m "add tasks table" && alembic upgrade head
```

- [ ] **Step 7: Commit**

```bash
git add backend/ && git commit -m "feat(backend): add background task model and manager with startup recovery"
```

---

### Task 7: Extraction Service + Extract Endpoint

**Files:**
- Create: `backend/app/services/extraction_service.py`
- Modify: `backend/app/api/sources.py` (add extract endpoint)
- Create: `backend/tests/test_extraction.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add extraction dependencies**

Append to `backend/requirements.txt`:
```
pdfminer.six==20231228
python-docx==1.1.2
python-pptx==1.0.2
openpyxl==3.1.5
```

Install: `pip install pdfminer.six==20231228 python-docx==1.1.2 python-pptx==1.0.2 openpyxl==3.1.5`

- [ ] **Step 2: Create extraction service**

```python
# backend/app/services/extraction_service.py
import io
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document as DocxDocument
from pptx import Presentation
from openpyxl import load_workbook

def extract_text(data: bytes, content_type: str) -> str:
    """Extract text from file data based on content type."""
    try:
        if content_type == "pdf":
            return _extract_pdf(data)
        elif content_type == "docx":
            return _extract_docx(data)
        elif content_type == "pptx":
            return _extract_pptx(data)
        elif content_type in ("xlsx", "xls", "ods"):
            return _extract_xlsx(data)
        elif content_type in ("txt", "md", "csv"):
            return data.decode("utf-8", errors="replace")
        elif content_type in ("png", "jpg", "jpeg", "webp"):
            return f"[Image file — extraction requires OpenRouter multimodal]"
        else:
            return f"[Unsupported format: {content_type}]"
    except Exception as e:
        return f"[Extraction failed: {str(e)}]"

def _extract_pdf(data: bytes) -> str:
    text = pdf_extract_text(io.BytesIO(data))
    if text and text.strip():
        return text.strip()
    return "[PDF appears to be scanned/image-based — extraction requires OpenRouter multimodal]"

def _extract_docx(data: bytes) -> str:
    doc = DocxDocument(io.BytesIO(data))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)

def _extract_pptx(data: bytes) -> str:
    prs = Presentation(io.BytesIO(data))
    slides_text = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    if para.text.strip():
                        texts.append(para.text.strip())
        if texts:
            slides_text.append(f"--- Slide {i} ---\n" + "\n".join(texts))
    return "\n\n".join(slides_text)

def _extract_xlsx(data: bytes) -> str:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheets_text = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            if any(cells):
                rows.append("\t".join(cells))
        if rows:
            sheets_text.append(f"--- {sheet_name} ---\n" + "\n".join(rows))
    wb.close()
    return "\n\n".join(sheets_text)
```

- [ ] **Step 3: Add extract endpoint to sources routes**

Append to `backend/app/api/sources.py`:

```python
from app.schemas.task import TaskResponse
from app.core.background import create_task, dispatch_background, update_task_status
from app.services.extraction_service import extract_text

async def _run_extraction(task_id, project_id, source_id):
    """Background extraction coroutine."""
    try:
        await update_task_status(task_id, "running", progress=10)
        async with __import__("app.db.session", fromlist=["async_session"]).async_session() as db:
            from app.services.source_service import get_source
            from app.core.storage import get_storage
            source = await get_source(db, project_id, source_id)
            storage = get_storage()
            data = await storage.read(source.storage_path)
            await update_task_status(task_id, "running", progress=50)
            text = extract_text(data, source.content_type)
            source.extracted_text = text
            source.status = "ready"
            await db.commit()
            await update_task_status(task_id, "completed", progress=100, result={"chars": len(text)})
    except Exception as e:
        await update_task_status(task_id, "failed", error=str(e))

@router.post("/{source_id}/extract", response_model=TaskResponse, status_code=202)
async def extract(project_id: uuid.UUID, source_id: uuid.UUID,
                  project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    source = await get_source(db, project.id, source_id)
    if source.status == "ready":
        raise HTTPException(status_code=400, detail="Source already extracted")
    from app.api.deps import get_current_user
    # Get user_id from the project owner
    from app.models.user import User
    task = await create_task(db, project.id, project.owner_id, "extraction", {"source_id": str(source_id)})
    dispatch_background(task.id, _run_extraction(task.id, project.id, source_id))
    return task
```

Note: The `_run_extraction` import pattern is ugly — the implementer should clean it up by importing properly at the top of the file. The key logic: read file from storage → call `extract_text()` → update source record → update task status.

- [ ] **Step 4: Create extraction tests**

```python
# backend/tests/test_extraction.py
from app.services.extraction_service import extract_text

def test_extract_txt():
    text = extract_text(b"hello world", "txt")
    assert text == "hello world"

def test_extract_csv():
    text = extract_text(b"a,b,c\n1,2,3", "csv")
    assert "a,b,c" in text

def test_extract_image_placeholder():
    text = extract_text(b"\x89PNG", "png")
    assert "OpenRouter" in text

def test_extract_unknown():
    text = extract_text(b"data", "xyz")
    assert "Unsupported" in text
```

- [ ] **Step 5: Run all tests**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v
```

Expected: All previous + 4 extraction + 7 source + 8 page tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat(backend): add extraction service and background task support"
```

---

### Task 8: Full Test Suite + Verification

- [ ] **Step 1: Run complete test suite**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v --tb=short
```

Expected counts:
- test_models: 1
- test_security: 5
- test_auth: 11
- test_projects: 6
- test_config: 3
- test_pages: 8
- test_sources: 7
- test_extraction: 4
- **Total: 45 tests**

- [ ] **Step 2: Verify API docs**

Start server and check Swagger UI:
```bash
uvicorn app.main:app --reload --port 8000
# Open http://localhost:8000/docs
# Verify new endpoints: pages/*, sources/*, sources/*/extract
```

- [ ] **Step 3: Final commit**

```bash
git add -A backend/ && git commit -m "feat(backend): complete Plan 2 — pages, sources, storage, extraction"
```

---

## Plan Summary

| Task | What | New Tests |
|------|------|-----------|
| 1 | Page model + schemas + migration | 0 |
| 2 | Page service + routes | 8 |
| 3 | Storage abstraction (LocalStorage) | 0 |
| 4 | Source model + schemas + migration | 0 |
| 5 | Source service + routes (upload, clip) | 7 |
| 6 | Background task model + manager | 0 |
| 7 | Extraction service + endpoint | 4 |
| 8 | Full test suite verification | 0 |

**After this plan:** Backend supports page CRUD, file upload/storage, web clipper, and document extraction. Ready for Plan 3 (LLM client, ingest pipeline, deep research, SSE streaming).
