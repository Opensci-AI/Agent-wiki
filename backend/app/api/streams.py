import asyncio
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, async_session
from app.core.security import decode_token
from app.core.llm_client import stream_chat
from app.core.sse import sse_token, sse_done, sse_error
from app.core.background import subscribe_task, unsubscribe_task
from app.services.auth_service import get_user_by_id
from app.services.chat_service import get_conversation, list_messages, add_message
from app.services.config_service import get_effective_config
from app.services.page_service import search_pages_for_rag
from app.api.deps import require_project_owner
from app.models.project import Project
from app.models.task import BackgroundTask

router = APIRouter(tags=["streams"])


async def _auth_from_query(token: str, db: AsyncSession):
    """Authenticate user from a query-param JWT (EventSource can't send headers)."""
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/api/v1/projects/{project_id}/stream/chat/{conv_id}")
async def stream_chat_sse(
    project_id: uuid.UUID,
    conv_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _auth_from_query(token, db)

    # Verify conversation ownership
    conv = await get_conversation(db, conv_id, user.id)

    # Load effective LLM config
    config = await get_effective_config(db, user.id)
    llm_config = config.get("llm_config")
    if not llm_config:
        raise HTTPException(status_code=400, detail="LLM not configured")

    # Load conversation messages
    messages = await list_messages(db, conv_id, limit=100)

    # Get the last user message for RAG search
    last_user_msg = None
    for m in reversed(messages):
        if m.role == "user":
            last_user_msg = m.content
            break

    # Search for relevant wiki pages (RAG)
    context_pages = []
    if last_user_msg:
        context_pages = await search_pages_for_rag(db, conv.project_id, last_user_msg, limit=5)

    # Build system prompt with context
    system_content = "You are a helpful assistant for a knowledge wiki. Answer questions based on the wiki content provided.\n\n"
    if context_pages:
        system_content += "## Relevant Wiki Pages:\n\n"
        for page in context_pages:
            system_content += f"### {page.title}\n{page.content[:2000]}\n\n"
        system_content += "---\nUse the above wiki content to answer the user's question. If the answer is not in the wiki, say so.\n"
    else:
        system_content += "No relevant wiki pages found. Answer based on your general knowledge but mention that there's no specific wiki content about this topic.\n"

    chat_messages = [{"role": "system", "content": system_content}]
    chat_messages += [{"role": m.role, "content": m.content} for m in messages]

    async def event_generator():
        full_response: list[str] = []
        try:
            async for tok in stream_chat(llm_config, chat_messages):
                full_response.append(tok)
                yield sse_token(tok)

            # Save assistant response to DB
            response_text = "".join(full_response)
            if response_text.strip():
                async with async_session() as save_db:
                    await add_message(save_db, conv_id, "assistant", response_text)

            yield sse_done()
        except Exception as exc:
            yield sse_error(str(exc))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/v1/tasks/{task_id}/stream")
async def stream_task_sse(
    task_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Stream real-time task progress updates via SSE.

    Events:
    - progress: {status, status_detail, current_step, progress_pct}
    - completed: {result}
    - error: {error}
    """
    user = await _auth_from_query(token, db)

    # Verify task ownership
    task = await db.scalar(select(BackgroundTask).where(BackgroundTask.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your task")

    async def event_generator():
        queue = subscribe_task(task_id)
        try:
            # Send initial state
            async with async_session() as inner_db:
                task = await inner_db.scalar(select(BackgroundTask).where(BackgroundTask.id == task_id))
                if task:
                    yield _format_task_event(task)

                    # If already completed/failed, end stream
                    if task.status in ("completed", "failed"):
                        return

            # Stream updates
            while True:
                try:
                    # Wait for update notification with timeout
                    await asyncio.wait_for(queue.get(), timeout=30.0)

                    # Fetch fresh task state
                    async with async_session() as inner_db:
                        task = await inner_db.scalar(select(BackgroundTask).where(BackgroundTask.id == task_id))
                        if task:
                            yield _format_task_event(task)

                            # End stream on completion/failure
                            if task.status in ("completed", "failed"):
                                return

                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield "event: heartbeat\ndata: {}\n\n"

        finally:
            unsubscribe_task(task_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_task_event(task: BackgroundTask) -> str:
    """Format task state as SSE event."""
    if task.status == "completed":
        data = {"status": "completed", "result": task.result}
        return f"event: completed\ndata: {json.dumps(data)}\n\n"
    elif task.status == "failed":
        data = {"status": "failed", "error": task.error}
        return f"event: error\ndata: {json.dumps(data)}\n\n"
    else:
        data = {
            "status": task.status,
            "status_detail": task.status_detail,
            "current_step": task.current_step,
            "progress_pct": task.progress_pct,
        }
        return f"event: progress\ndata: {json.dumps(data)}\n\n"
