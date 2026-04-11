# LLM Wiki — Karpathy Architecture Alignment

**Date:** 2026-04-11
**Status:** Approved
**Scope:** Align backend with Karpathy's LLM Wiki pattern (index.md, log.md, Schema, Export)

## Problem

Current implementation deviates from Karpathy's original design:
- Missing `index.md` (content catalog)
- Missing `log.md` (operation history)
- No Obsidian export (wiki stored in DB only)
- YAML frontmatter stored as JSON, not rendered

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| index.md storage | Materialized view (cached query) | Performance at scale, auto-invalidate |
| log.md storage | Separate table + render on read | Append-only, fast writes |
| Schema storage | Project field + export to schema.md | Single source of truth |
| Export format | ZIP with Obsidian vault structure | Full compatibility |
| Frontmatter | JSON in DB, render YAML on export | Best of both worlds |

---

## 1. Database Changes

### 1.1 New Table: operation_logs

```sql
CREATE TABLE operation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    operation VARCHAR(50) NOT NULL,
    title VARCHAR(500),
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_operation_logs_project_time 
    ON operation_logs(project_id, created_at DESC);
```

**Operations:**
- `ingest` — source processed, pages created/updated
- `query` — chat query answered (optional, for audit)
- `lint` — lint pass completed
- `export` — vault exported
- `page_create` — manual page creation
- `page_update` — manual page edit
- `page_delete` — page deleted

**Details JSONB examples:**
```json
// ingest
{
  "source_id": "uuid",
  "source_name": "paper.pdf",
  "pages_created": ["wiki/entities/anthropic.md"],
  "pages_updated": ["wiki/entities/claude.md"],
  "duration_ms": 5200
}

// lint
{
  "issues_found": 12,
  "broken_links": 8,
  "orphan_pages": 4
}
```

### 1.2 Pages Table Frontmatter Schema

Ensure all pages have standardized frontmatter:

```json
{
  "sources": ["paper.pdf", "article.md"],
  "tags": ["ai", "llm"],
  "created": "2026-04-11T10:30:00Z",
  "updated": "2026-04-11T14:22:00Z",
  "summary": "One-line description for index.md"
}
```

---

## 2. index.md Generation

### 2.1 Service Function

```python
async def generate_index_md(db: AsyncSession, project_id: UUID) -> str:
    """Generate index.md content from pages table."""
    pages = await db.execute(
        select(Page)
        .where(Page.project_id == project_id)
        .order_by(Page.type, Page.title)
    )
    
    # Group by type
    grouped: dict[str, list[Page]] = {}
    for page in pages.scalars():
        grouped.setdefault(page.type, []).append(page)
    
    # Render markdown
    lines = ["# Wiki Index\n"]
    lines.append(f"*{sum(len(v) for v in grouped.values())} pages*\n")
    
    for page_type in ["entity", "concept", "query", "general"]:
        if page_type not in grouped:
            continue
        lines.append(f"\n## {page_type.title()}s\n")
        for page in grouped[page_type]:
            summary = page.frontmatter.get("summary", "")
            source_count = len(page.frontmatter.get("sources", []))
            lines.append(f"- [[{page.path}|{page.title}]]")
            if summary:
                lines.append(f" — {summary}")
            if source_count:
                lines.append(f" ({source_count} sources)")
            lines.append("\n")
    
    return "".join(lines)
```

### 2.2 Caching Strategy

- Cache in Redis/memory with key `index_md:{project_id}`
- Invalidate on: page create, update, delete
- TTL: 5 minutes (fallback if invalidation missed)

```python
async def invalidate_index_cache(project_id: UUID) -> None:
    """Invalidate cached index.md for a project."""
    cache_key = f"index_md:{project_id}"
    # Using simple dict cache for now, replace with Redis if needed
    _index_cache.pop(cache_key, None)
```

---

## 3. log.md Generation

### 3.1 Service Function

```python
async def generate_log_md(
    db: AsyncSession, 
    project_id: UUID, 
    limit: int = 100
) -> str:
    """Generate log.md content from operation_logs table."""
    logs = await db.execute(
        select(OperationLog)
        .where(OperationLog.project_id == project_id)
        .order_by(OperationLog.created_at.desc())
        .limit(limit)
    )
    
    lines = ["# Operation Log\n"]
    
    for log in logs.scalars():
        date = log.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"## [{date}] {log.operation}")
        if log.title:
            lines.append(f" | {log.title}")
        lines.append("\n")
        
        # Add details based on operation type
        if log.operation == "ingest":
            details = log.details
            if details.get("pages_created"):
                lines.append(f"- Created: {', '.join(details['pages_created'])}\n")
            if details.get("pages_updated"):
                lines.append(f"- Updated: {', '.join(details['pages_updated'])}\n")
        
        lines.append("\n")
    
    return "".join(lines)
```

### 3.2 Log Entry Function

```python
async def append_operation_log(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID | None,
    operation: str,
    title: str = "",
    details: dict = {}
) -> OperationLog:
    """Append entry to operation_logs table."""
    log = OperationLog(
        project_id=project_id,
        user_id=user_id,
        operation=operation,
        title=title,
        details=details
    )
    db.add(log)
    await db.commit()
    return log
```

---

## 4. Export API

### 4.1 Endpoint

```
GET /api/v1/projects/:id/export
    ?format=obsidian    (default)
    &include_raw=false  (include source files)
    
Response: application/zip
Filename: {project_name}-wiki-{date}.zip
```

### 4.2 ZIP Structure

```
project-name/
├── .obsidian/
│   └── app.json              # Basic Obsidian config
├── schema.md                 # From project.schema_text
├── purpose.md                # From project.purpose
├── wiki/
│   ├── index.md              # Generated
│   ├── log.md                # Generated
│   ├── entities/
│   │   └── *.md              # With YAML frontmatter
│   ├── concepts/
│   │   └── *.md
│   └── sources/
│       └── *.md
└── raw/                      # If include_raw=true
    └── *.pdf, *.md, etc.
```

### 4.3 Page Export Format

```markdown
---
title: Anthropic
type: entity
path: wiki/entities/anthropic.md
sources:
  - paper.pdf
  - article.md
tags:
  - ai-company
  - llm
created: 2026-04-11T10:30:00Z
updated: 2026-04-11T14:22:00Z
---

# Anthropic

Anthropic is an AI safety company...

## Related

- [[wiki/entities/claude.md|Claude]]
- [[wiki/concepts/constitutional-ai.md|Constitutional AI]]
```

### 4.4 Export Service

```python
async def export_obsidian_vault(
    db: AsyncSession,
    project_id: UUID,
    include_raw: bool = False
) -> bytes:
    """Export project as Obsidian vault ZIP."""
    project = await get_project(db, project_id)
    pages = await list_pages(db, project_id)
    
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # .obsidian/app.json
        zf.writestr(f"{project.name}/.obsidian/app.json", '{}')
        
        # schema.md
        if project.schema_text:
            zf.writestr(f"{project.name}/schema.md", project.schema_text)
        
        # purpose.md
        if project.purpose:
            zf.writestr(
                f"{project.name}/purpose.md",
                f"# Purpose\n\n{project.purpose}"
            )
        
        # wiki/index.md
        index_content = await generate_index_md(db, project_id)
        zf.writestr(f"{project.name}/wiki/index.md", index_content)
        
        # wiki/log.md
        log_content = await generate_log_md(db, project_id)
        zf.writestr(f"{project.name}/wiki/log.md", log_content)
        
        # wiki pages
        for page in pages:
            content = render_page_with_frontmatter(page)
            zf.writestr(f"{project.name}/{page.path}", content)
        
        # raw sources (optional)
        if include_raw:
            sources = await list_sources(db, project_id)
            for source in sources:
                data = await storage.read(source.storage_path)
                zf.writestr(
                    f"{project.name}/raw/{source.filename}",
                    data
                )
    
    buffer.seek(0)
    return buffer.read()


def render_page_with_frontmatter(page: Page) -> str:
    """Render page content with YAML frontmatter."""
    frontmatter = {
        "title": page.title,
        "type": page.type,
        "path": page.path,
        **page.frontmatter
    }
    
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    
    return f"---\n{yaml_str}---\n\n{page.content}"
```

---

## 5. Updated Ingest Flow

### 5.1 Modified ingest_service.py

```python
async def run_ingest(
    task_id: UUID,
    project_id: UUID,
    source_id: UUID,
    user_id: UUID,
    llm_config: dict,
) -> None:
    """Ingest source into wiki pages."""
    
    # ... existing code ...
    
    # After parsing FILE blocks and writing pages:
    
    # 5.1 Invalidate index.md cache
    await invalidate_index_cache(project_id)
    
    # 5.2 Append to operation_logs
    await append_operation_log(
        db,
        project_id=project_id,
        user_id=user_id,
        operation="ingest",
        title=source.filename,
        details={
            "source_id": str(source_id),
            "source_name": source.filename,
            "pages_created": [p for p in written_paths if p not in existing_paths],
            "pages_updated": [p for p in written_paths if p in existing_paths],
            "reviews": len(reviews),
        }
    )
```

### 5.2 Generation Prompt Update

Include schema, purpose, and current index in context:

```python
gen_messages = [
    {
        "role": "system",
        "content": f"""You are a wiki page generator following these rules:

## Wiki Schema
{project.schema_text}

## Wiki Purpose  
{project.purpose}

## Current Index
{current_index_md}

Generate wiki pages from the analysis. Output format:
---FILE: wiki/entities/<slug>.md---
---
title: Page Title
type: entity
sources:
  - {source.filename}
summary: One-line description
---

# Page Title

Content with [[wikilinks]]...
---END FILE---
"""
    },
    {"role": "user", "content": f"Generate wiki pages from:\n\n{analysis}"}
]
```

---

## 6. API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects/:id/wiki/index` | Get index.md content |
| GET | `/projects/:id/wiki/log` | Get log.md content |
| GET | `/projects/:id/export` | Export Obsidian vault ZIP |
| GET | `/projects/:id/logs` | List operation logs (JSON) |

---

## 7. File Changes

| File | Change |
|------|--------|
| `models/operation_log.py` | New model |
| `schemas/wiki.py` | New: OperationLogResponse, IndexResponse |
| `services/wiki_service.py` | New: generate_index_md, generate_log_md, invalidate_index_cache |
| `services/log_service.py` | New: append_operation_log, list_logs |
| `services/export_service.py` | New: export_obsidian_vault, render_page_with_frontmatter |
| `services/ingest_service.py` | Update: add logging, invalidate cache, pass user_id |
| `api/wiki.py` | New: index, log, export endpoints |
| `api/ingest.py` | Update: pass user_id to run_ingest |
| `alembic/versions/xxx_add_operation_logs.py` | Migration |
| `requirements.txt` | Add: pyyaml |

### 7.1 New Schemas

```python
# schemas/wiki.py
from pydantic import BaseModel
from datetime import datetime
from typing import Any

class OperationLogResponse(BaseModel):
    id: str
    operation: str
    title: str | None
    details: dict[str, Any]
    created_at: datetime

class IndexResponse(BaseModel):
    content: str
    page_count: int
    generated_at: datetime
```

---

## 8. Success Criteria

- [ ] `GET /projects/:id/wiki/index` returns formatted index.md
- [ ] `GET /projects/:id/wiki/log` returns formatted log.md
- [ ] Ingest operation appends to operation_logs
- [ ] Export produces valid Obsidian vault ZIP
- [ ] Pages export with YAML frontmatter
- [ ] index.md cache invalidates on page changes
