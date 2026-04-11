# Karpathy Architecture Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align LLM Wiki backend with Karpathy's original design pattern (index.md, log.md, operation logging, Obsidian export).

**Architecture:** Add operation_logs table for tracking all wiki operations. Generate index.md and log.md dynamically from DB with caching. Export API creates Obsidian-compatible ZIP vault with YAML frontmatter.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, PyYAML, zipfile

---

## File Structure

```
backend/app/
├── models/
│   └── operation_log.py          # NEW: OperationLog model
├── schemas/
│   └── wiki.py                   # NEW: OperationLogResponse, IndexResponse, LogResponse
├── services/
│   ├── wiki_service.py           # NEW: generate_index_md, generate_log_md, cache
│   ├── log_service.py            # NEW: append_operation_log, list_logs
│   └── export_service.py         # NEW: export_obsidian_vault
├── api/
│   └── wiki.py                   # NEW: /wiki/index, /wiki/log, /export, /logs
└── main.py                       # MODIFY: add wiki router

backend/
├── requirements.txt              # MODIFY: add pyyaml
└── alembic/versions/
    └── xxxx_add_operation_logs.py  # NEW: migration
```

---

### Task 1: Add PyYAML Dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add pyyaml to requirements**

```bash
echo "pyyaml==6.0.2" >> backend/requirements.txt
```

- [ ] **Step 2: Install dependency**

Run: `pip install pyyaml==6.0.2`
Expected: Successfully installed pyyaml

- [ ] **Step 3: Verify import works**

Run: `python -c "import yaml; print(yaml.__version__)"`
Expected: `6.0.2`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add pyyaml for YAML frontmatter export"
```

---

### Task 2: Create OperationLog Model

**Files:**
- Create: `backend/app/models/operation_log.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create OperationLog model**

```python
# backend/app/models/operation_log.py
import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    operation: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
```

- [ ] **Step 2: Export from models/__init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.operation_log import OperationLog
```

- [ ] **Step 3: Create migration**

Run: `cd backend && alembic revision --autogenerate -m "add_operation_logs_table"`
Expected: Migration file created

- [ ] **Step 4: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applied successfully

- [ ] **Step 5: Verify table exists**

Run: `psql -d llm_wiki -c "\d operation_logs"`
Expected: Table structure displayed

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/operation_log.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat: add OperationLog model and migration"
```

---

### Task 3: Create Wiki Schemas

**Files:**
- Create: `backend/app/schemas/wiki.py`

- [ ] **Step 1: Create wiki schemas**

```python
# backend/app/schemas/wiki.py
from pydantic import BaseModel
from datetime import datetime
from typing import Any


class OperationLogResponse(BaseModel):
    id: str
    project_id: str
    user_id: str | None
    operation: str
    title: str | None
    details: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class IndexResponse(BaseModel):
    content: str
    page_count: int
    generated_at: datetime


class LogResponse(BaseModel):
    content: str
    entry_count: int
    generated_at: datetime


class ExportRequest(BaseModel):
    include_raw: bool = False
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/wiki.py
git commit -m "feat: add wiki-related Pydantic schemas"
```

---

### Task 4: Create Wiki Service

**Files:**
- Create: `backend/app/services/wiki_service.py`

- [ ] **Step 1: Create wiki_service.py**

```python
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
            if details.get("pages_created"):
                lines.append(f"- Created: {', '.join(details['pages_created'])}\n")
            if details.get("pages_updated"):
                lines.append(f"- Updated: {', '.join(details['pages_updated'])}\n")
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/wiki_service.py
git commit -m "feat: add wiki service for index.md and log.md generation"
```

---

### Task 5: Create Log Service

**Files:**
- Create: `backend/app/services/log_service.py`

- [ ] **Step 1: Create log_service.py**

```python
# backend/app/services/log_service.py
"""Operation logging service."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operation_log import OperationLog


async def append_operation_log(
    db: AsyncSession,
    project_id: uuid.UUID,
    operation: str,
    title: str = "",
    details: dict[str, Any] | None = None,
    user_id: uuid.UUID | None = None,
) -> OperationLog:
    """Append entry to operation_logs table."""
    log = OperationLog(
        project_id=project_id,
        user_id=user_id,
        operation=operation,
        title=title or None,
        details=details or {},
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_operation_logs(
    db: AsyncSession,
    project_id: uuid.UUID,
    operation: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[OperationLog]:
    """List operation logs for a project."""
    query = select(OperationLog).where(OperationLog.project_id == project_id)
    
    if operation:
        query = query.where(OperationLog.operation == operation)
    
    query = query.order_by(OperationLog.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    return list(result.scalars().all())
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/log_service.py
git commit -m "feat: add operation logging service"
```

---

### Task 6: Create Export Service

**Files:**
- Create: `backend/app/services/export_service.py`

- [ ] **Step 1: Create export_service.py**

```python
# backend/app/services/export_service.py
"""Obsidian vault export service."""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page
from app.models.project import Project
from app.services.project_service import get_project
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


async def export_obsidian_vault(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    include_raw: bool = False,
) -> tuple[bytes, str]:
    """Export project as Obsidian vault ZIP.
    
    Returns: (zip_bytes, filename)
    """
    project = await get_project(db, project_id)
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/export_service.py
git commit -m "feat: add Obsidian vault export service"
```

---

### Task 7: Create Wiki API Router

**Files:**
- Create: `backend/app/api/wiki.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create wiki.py router**

```python
# backend/app/api/wiki.py
"""Wiki API endpoints for index.md, log.md, and export."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.api.deps import require_project_owner
from app.schemas.wiki import IndexResponse, LogResponse, OperationLogResponse
from app.services.wiki_service import generate_index_md, generate_log_md
from app.services.log_service import list_operation_logs
from app.services.export_service import export_obsidian_vault


router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["wiki"])


@router.get("/wiki/index", response_model=IndexResponse)
async def get_wiki_index(
    project_id: uuid.UUID,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """Get generated index.md content."""
    content, page_count = await generate_index_md(db, project_id)
    return IndexResponse(
        content=content,
        page_count=page_count,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/wiki/log", response_model=LogResponse)
async def get_wiki_log(
    project_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """Get generated log.md content."""
    content, entry_count = await generate_log_md(db, project_id, limit=limit)
    return LogResponse(
        content=content,
        entry_count=entry_count,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/logs", response_model=list[OperationLogResponse])
async def get_operation_logs(
    project_id: uuid.UUID,
    operation: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """List operation logs as JSON."""
    logs = await list_operation_logs(
        db, project_id, operation=operation, limit=limit, offset=offset
    )
    return [
        OperationLogResponse(
            id=str(log.id),
            project_id=str(log.project_id),
            user_id=str(log.user_id) if log.user_id else None,
            operation=log.operation,
            title=log.title,
            details=log.details or {},
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/export")
async def export_vault(
    project_id: uuid.UUID,
    include_raw: bool = Query(False),
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    """Export project as Obsidian vault ZIP."""
    # Get user_id from project owner check
    user_id = project.owner_id
    
    zip_bytes, filename = await export_obsidian_vault(
        db, project_id, user_id=user_id, include_raw=include_raw
    )
    
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 2: Register router in main.py**

Add to `backend/app/main.py` after other router imports:

```python
from app.api.wiki import router as wiki_router
app.include_router(wiki_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/wiki.py backend/app/main.py
git commit -m "feat: add wiki API endpoints (index, log, export)"
```

---

### Task 8: Update Ingest Service with Logging

**Files:**
- Modify: `backend/app/services/ingest_service.py`

- [ ] **Step 1: Add imports to ingest_service.py**

Add at top of file:

```python
from app.services.wiki_service import invalidate_index_cache
from app.services.log_service import append_operation_log
```

- [ ] **Step 2: Update run_ingest function signature**

Change function signature to include user_id:

```python
async def run_ingest(
    task_id: uuid.UUID,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    user_id: uuid.UUID | None,  # ADD THIS
    llm_config: dict,
) -> None:
```

- [ ] **Step 3: Add logging and cache invalidation**

After the line `await db.commit()` that commits pages (around line 245), add:

```python
        # Track which paths existed before vs created new
        existing_paths_set = set()  # Populate this before the loop if needed
        
        # Invalidate index cache
        invalidate_index_cache(project_id)
        
        # Log the ingest operation
        await append_operation_log(
            db,
            project_id=project_id,
            user_id=user_id,
            operation="ingest",
            title=source.filename,
            details={
                "source_id": str(source_id),
                "source_name": source.filename,
                "pages_written": len(written_paths),
                "paths": written_paths,
            }
        )
```

- [ ] **Step 4: Update ingest API to pass user_id**

In `backend/app/api/ingest.py`, update the `run_ingest` call to include user_id from the authenticated user.

- [ ] **Step 5: Test ingest still works**

Run: Upload a source and trigger ingest via API
Expected: Ingest completes, operation_logs table has entry

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ingest_service.py backend/app/api/ingest.py
git commit -m "feat: add operation logging to ingest service"
```

---

### Task 9: Integration Testing

**Files:**
- Test via API calls

- [ ] **Step 1: Test index.md endpoint**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/projects/$PROJECT_ID/wiki/index"
```

Expected: JSON with `content`, `page_count`, `generated_at`

- [ ] **Step 2: Test log.md endpoint**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/projects/$PROJECT_ID/wiki/log"
```

Expected: JSON with `content`, `entry_count`, `generated_at`

- [ ] **Step 3: Test operation logs endpoint**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/projects/$PROJECT_ID/logs"
```

Expected: JSON array of operation log entries

- [ ] **Step 4: Test export endpoint**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/projects/$PROJECT_ID/export" \
  -o vault.zip && unzip -l vault.zip
```

Expected: ZIP file with schema.md, purpose.md, wiki/index.md, wiki/log.md, wiki pages

- [ ] **Step 5: Verify YAML frontmatter in exported pages**

```bash
unzip vault.zip && head -20 */wiki/entities/*.md
```

Expected: Pages start with `---` YAML frontmatter block

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test: verify Karpathy architecture alignment"
```

---

## Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | Add PyYAML dependency | 2 min |
| 2 | Create OperationLog model + migration | 10 min |
| 3 | Create wiki schemas | 5 min |
| 4 | Create wiki service (index.md, log.md) | 15 min |
| 5 | Create log service | 10 min |
| 6 | Create export service | 15 min |
| 7 | Create wiki API router | 10 min |
| 8 | Update ingest with logging | 10 min |
| 9 | Integration testing | 10 min |

**Total: ~90 minutes**
