"""Deep research pipeline: web search + LLM synthesis -> wiki page."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.core.background import update_task_status
from app.core.llm_client import complete_chat
from app.core.web_search import tavily_search
from app.db.session import async_session
from app.models.page import Page


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")[:60]


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> blocks from LLM output."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


async def run_research(
    task_id: uuid.UUID,
    project_id: uuid.UUID,
    topic: str,
    search_queries: list[str],
    llm_config: dict,
    search_api_key: str,
) -> None:
    """Background coroutine: web search -> LLM synthesis -> save wiki page.

    Steps:
    1. Run web searches for each query (deduplicate results)
    2. LLM synthesis from search results
    3. Strip <think> blocks
    4. Save as wiki page
    """
    await update_task_status(task_id, "running", progress=0)

    try:
        # 1. Web search (deduplicated)
        all_results: list[dict] = []
        seen_urls: set[str] = set()

        for i, query in enumerate(search_queries):
            results = await tavily_search(query, search_api_key, max_results=5)
            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)

            progress = int((i + 1) / len(search_queries) * 40)
            await update_task_status(task_id, "running", progress=progress)

        if not all_results:
            await update_task_status(
                task_id, "failed", error="No search results found"
            )
            return

        await update_task_status(task_id, "running", progress=50)

        # 2. LLM synthesis
        sources_text = "\n\n".join(
            f"### {r['title']}\nURL: {r['url']}\nSource: {r['source']}\n{r['snippet']}"
            for r in all_results
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research synthesizer. ALWAYS write in Vietnamese.\n"
                    "Write a comprehensive, well-organized wiki page about the given topic "
                    "based on the search results provided. "
                    "Include citations as [Source](URL). Use markdown formatting with "
                    "headings, bullet points, and tables where appropriate.\n"
                    "ALL content must be in Vietnamese."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Chủ đề: {topic}\n\n"
                    f"Kết quả tìm kiếm:\n\n{sources_text}"
                ),
            },
        ]

        synthesis = await complete_chat(llm_config, messages)

        await update_task_status(task_id, "running", progress=80)

        # 3. Strip <think> blocks
        clean_content = _strip_think_blocks(synthesis)

        # 4. Save as wiki page
        slug = _slugify(topic)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        page_path = f"wiki/queries/research-{slug}-{date_str}.md"

        async with async_session() as db:
            page = Page(
                id=uuid.uuid4(),
                project_id=project_id,
                path=page_path,
                type="query",
                title=f"Research: {topic}",
                content=clean_content,
                frontmatter={
                    "topic": topic,
                    "search_queries": search_queries,
                    "sources": [r["url"] for r in all_results],
                    "date": date_str,
                },
            )
            db.add(page)
            await db.commit()

        await update_task_status(
            task_id,
            "completed",
            progress=100,
            result={
                "page_path": page_path,
                "sources_count": len(all_results),
                "topic": topic,
            },
        )

    except Exception as exc:
        await update_task_status(task_id, "failed", error=str(exc))
