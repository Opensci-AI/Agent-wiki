"""Ingest pipeline: parse source text -> LLM analysis -> generate wiki pages."""

from __future__ import annotations

import hashlib
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background import update_task_status
from app.core.llm_client import complete_chat
from app.db.session import async_session
from app.models.ingest_cache import IngestCache
from app.models.page import Page
from app.models.source import Source
from app.services.wiki_service import invalidate_index_cache
from app.services.log_service import append_operation_log


# ---------------------------------------------------------------------------
# Block parsers
# ---------------------------------------------------------------------------

def parse_file_blocks(text: str) -> list[tuple[str, str]]:
    """Extract (path, content) tuples from ---FILE: ... ---END FILE--- blocks."""
    pattern = r"---FILE:\s*([^\n-]+?)\s*---\n([\s\S]*?)---END FILE---"
    return re.findall(pattern, text)


def parse_review_blocks(text: str, source_path: str = "") -> list[dict]:
    """Extract review items from ---REVIEW: type | title ---END REVIEW--- blocks."""
    pattern = r"---REVIEW:\s*(\w[\w-]*)\s*\|\s*(.+?)\s*---\n([\s\S]*?)---END REVIEW---"
    reviews: list[dict] = []
    for match in re.finditer(pattern, text):
        review_type = match.group(1).strip()
        title = match.group(2).strip()
        body = match.group(3).strip()

        # Parse structured lines from body
        options: list[str] = []
        pages: list[str] = []
        search_queries: list[str] = []
        description_lines: list[str] = []

        for line in body.split("\n"):
            line_stripped = line.strip()
            if line_stripped.startswith("OPTIONS:"):
                options = [o.strip() for o in line_stripped[8:].split("|") if o.strip()]
            elif line_stripped.startswith("PAGES:"):
                pages = [p.strip() for p in line_stripped[6:].split(",") if p.strip()]
            elif line_stripped.startswith("SEARCH:"):
                search_queries = [
                    q.strip() for q in line_stripped[7:].split("|") if q.strip()
                ]
            else:
                description_lines.append(line_stripped)

        reviews.append(
            {
                "type": review_type,
                "title": title,
                "description": "\n".join(description_lines).strip(),
                "options": options,
                "pages": pages,
                "search_queries": search_queries,
                "source": source_path,
            }
        )
    return reviews


# ---------------------------------------------------------------------------
# Background pipeline
# ---------------------------------------------------------------------------

async def run_ingest(
    task_id: uuid.UUID,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    user_id: uuid.UUID | None,
    llm_config: dict,
) -> None:
    """Background coroutine: ingest a source into wiki pages.

    Steps:
    1. Load source text
    2. Check cache (skip if unchanged)
    3. Analysis step (LLM)
    4. Generation step (LLM)
    5. Parse FILE blocks -> write pages to DB
    6. Parse REVIEW blocks -> store in task result
    7. Update cache
    """
    await update_task_status(
        task_id, "running", progress=0,
        detail="Initializing ingest pipeline...",
        step="init"
    )

    try:
        async with async_session() as db:
            # 1. Load source
            await update_task_status(
                task_id, "running", progress=5,
                detail="Loading source document...",
                step="load_source"
            )

            result = await db.execute(
                select(Source).where(
                    Source.id == source_id, Source.project_id == project_id
                )
            )
            source = result.scalar_one_or_none()
            if not source:
                await update_task_status(
                    task_id, "failed", error="Source not found"
                )
                return

            source_text = source.extracted_text or ""
            if not source_text.strip():
                await update_task_status(
                    task_id, "failed", error="Source has no extracted text"
                )
                return

            # 2. Check cache
            await update_task_status(
                task_id, "running", progress=8,
                detail="Checking for changes since last ingest...",
                step="check_cache"
            )

            content_hash = hashlib.sha256(source_text.encode()).hexdigest()
            cache_result = await db.execute(
                select(IngestCache).where(
                    IngestCache.project_id == project_id,
                    IngestCache.source_filename == source.filename,
                )
            )
            cache = cache_result.scalar_one_or_none()
            if cache and cache.content_hash == content_hash:
                await update_task_status(
                    task_id,
                    "completed",
                    progress=100,
                    result={"skipped": True, "reason": "Content unchanged"},
                )
                return

        await update_task_status(
            task_id, "running", progress=10,
            detail=f"Loaded '{source.filename}' ({len(source_text):,} chars)",
            step="source_loaded"
        )

        # 3. Analysis step
        await update_task_status(
            task_id, "running", progress=15,
            detail="Analyzing document with AI (identifying entities & concepts)...",
            step="llm_analysis"
        )

        analysis_messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert knowledge analyst. Analyze the following source "
                    "material and identify:\n"
                    "1. Key entities (people, organizations, tools, frameworks)\n"
                    "2. Key concepts (ideas, theories, methods)\n"
                    "3. Relationships between them\n"
                    "4. Any contradictions or items needing verification\n\n"
                    "Be thorough and specific. List at least 5-10 entities and 3-5 concepts."
                ),
            },
            {"role": "user", "content": f"Analyze this source:\n\n{source_text[:50000]}"},
        ]
        analysis = await complete_chat(llm_config, analysis_messages)

        await update_task_status(
            task_id, "running", progress=40,
            detail="Analysis complete. Generating wiki pages...",
            step="analysis_complete"
        )

        # 4. Generation step
        await update_task_status(
            task_id, "running", progress=45,
            detail="Generating wiki pages from analysis...",
            step="llm_generation"
        )

        gen_messages = [
            {
                "role": "system",
                "content": (
                    "You are a wiki page generator. You MUST generate wiki pages from the analysis.\n\n"
                    "OUTPUT FORMAT — you MUST use this exact format for EVERY page:\n\n"
                    "---FILE: wiki/entities/<slug>.md---\n"
                    "# Entity Title\n\n"
                    "Description and details...\n\n"
                    "## Related\n"
                    "- [[Other Page]]\n"
                    "---END FILE---\n\n"
                    "Categories for <slug> paths:\n"
                    "- wiki/entities/ — for people, orgs, tools, frameworks\n"
                    "- wiki/concepts/ — for ideas, theories, methods\n"
                    "- wiki/overview/ — for summary/index pages\n\n"
                    "RULES:\n"
                    "- Generate AT LEAST 3 pages, ideally 5-10\n"
                    "- Use [[wikilinks]] to cross-reference between pages\n"
                    "- Each page should have substantive content (100+ words)\n"
                    "- Slugs must be lowercase-kebab-case\n\n"
                    "After all FILE blocks, optionally flag contradictions:\n\n"
                    "---REVIEW: <type> | <title>---\n"
                    "Description\n"
                    "PAGES: wiki/path1.md, wiki/path2.md\n"
                    "---END REVIEW---\n\n"
                    "Valid review types: Contradiction, Suggestion, Missing-Page\n\n"
                    "START OUTPUT WITH ---FILE: immediately. Do not add preamble."
                ),
            },
            {"role": "user", "content": f"Generate wiki pages from this analysis:\n\n{analysis}"},
        ]
        generation = await complete_chat(llm_config, gen_messages)

        await update_task_status(
            task_id, "running", progress=70,
            detail="Parsing generated content...",
            step="parse_generation"
        )

        # 5. Parse FILE blocks -> write pages to DB
        file_blocks = parse_file_blocks(generation)
        written_paths: list[str] = []
        total_pages = len(file_blocks)

        await update_task_status(
            task_id, "running", progress=72,
            detail=f"Found {total_pages} wiki pages to write...",
            step="pages_found"
        )

        async with async_session() as db:
            for idx, (path, content) in enumerate(file_blocks):
                path = path.strip()
                # Determine type from path
                if "/entities/" in path:
                    page_type = "entity"
                elif "/concepts/" in path:
                    page_type = "concept"
                elif "/queries/" in path:
                    page_type = "query"
                else:
                    page_type = "general"

                # Extract title from first heading
                title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else path.split("/")[-1].replace(".md", "")

                # Upsert page
                existing = await db.execute(
                    select(Page).where(
                        Page.project_id == project_id, Page.path == path
                    )
                )
                page = existing.scalar_one_or_none()
                if page:
                    page.content = content.strip()
                    page.title = title
                    page.frontmatter = {
                        **page.frontmatter,
                        "sources": list(
                            set(page.frontmatter.get("sources", []) + [source.filename])
                        ),
                    }
                else:
                    page = Page(
                        id=uuid.uuid4(),
                        project_id=project_id,
                        path=path,
                        type=page_type,
                        title=title,
                        content=content.strip(),
                        frontmatter={"sources": [source.filename]},
                    )
                    db.add(page)

                written_paths.append(path)

                # Update progress for each page written
                page_progress = 72 + int((idx + 1) / max(total_pages, 1) * 10)  # 72-82%
                await update_task_status(
                    task_id, "running", progress=page_progress,
                    detail=f"Writing page {idx + 1}/{total_pages}: {title}",
                    step="write_pages"
                )

            await update_task_status(
                task_id, "running", progress=83,
                detail="Saving pages to database...",
                step="commit_pages"
            )

            await db.commit()

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

        await update_task_status(
            task_id, "running", progress=88,
            detail="Processing review items & updating cache...",
            step="process_reviews"
        )

        # 6. Parse REVIEW blocks
        reviews = parse_review_blocks(generation, source.filename)

        await update_task_status(
            task_id, "running", progress=92,
            detail="Updating ingest cache...",
            step="update_cache"
        )

        # 7. Update cache
        async with async_session() as db:
            cache_result = await db.execute(
                select(IngestCache).where(
                    IngestCache.project_id == project_id,
                    IngestCache.source_filename == source.filename,
                )
            )
            cache = cache_result.scalar_one_or_none()
            if cache:
                cache.content_hash = content_hash
                cache.written_paths = written_paths
            else:
                db.add(
                    IngestCache(
                        project_id=project_id,
                        source_filename=source.filename,
                        content_hash=content_hash,
                        written_paths=written_paths,
                    )
                )
            await db.commit()

        await update_task_status(
            task_id, "running", progress=98,
            detail=f"Finalizing... Created {len(written_paths)} wiki pages",
            step="finalizing"
        )

        await update_task_status(
            task_id,
            "completed",
            progress=100,
            result={
                "pages_written": len(written_paths),
                "paths": written_paths,
                "reviews": reviews,
            },
        )

    except Exception as exc:
        await update_task_status(task_id, "failed", error=str(exc))
