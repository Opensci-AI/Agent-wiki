import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session
from app.models.task import BackgroundTask

_running_tasks: dict[uuid.UUID, asyncio.Task] = {}

async def recover_orphaned_tasks():
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

async def update_task_status(
    task_id: uuid.UUID,
    status: str,
    progress: int = 0,
    result: dict | None = None,
    error: str | None = None,
    detail: str | None = None,
    step: str | None = None,
):
    """Update task status with optional detailed progress info.

    Args:
        task_id: Task UUID
        status: Status string (queued, running, completed, failed)
        progress: Progress percentage (0-100)
        result: Final result dict
        error: Error message if failed
        detail: Human-readable description of current step (e.g., "Extracting text from PDF...")
        step: Machine-readable step identifier (e.g., "extract_text", "llm_analyze")
    """
    async with async_session() as db:
        values = dict(status=status, progress_pct=progress, updated_at=datetime.now(timezone.utc))
        if result is not None:
            values["result"] = result
        if error is not None:
            values["error"] = error
        if detail is not None:
            values["status_detail"] = detail
        if step is not None:
            values["current_step"] = step
        if status == "running":
            values["started_at"] = datetime.now(timezone.utc)
        if status in ("completed", "failed"):
            values["completed_at"] = datetime.now(timezone.utc)
            values["status_detail"] = None  # Clear detail on completion
            values["current_step"] = None
        await db.execute(update(BackgroundTask).where(BackgroundTask.id == task_id).values(**values))
        await db.commit()

        # Notify SSE subscribers
        await _notify_task_update(task_id)


# SSE subscribers for real-time task updates
_task_subscribers: dict[uuid.UUID, list[asyncio.Queue]] = {}


async def _notify_task_update(task_id: uuid.UUID):
    """Notify all SSE subscribers about task update."""
    if task_id in _task_subscribers:
        for queue in _task_subscribers[task_id]:
            try:
                await queue.put(task_id)
            except Exception:
                pass


def subscribe_task(task_id: uuid.UUID) -> asyncio.Queue:
    """Subscribe to task updates, returns a queue that receives notifications."""
    queue: asyncio.Queue = asyncio.Queue()
    if task_id not in _task_subscribers:
        _task_subscribers[task_id] = []
    _task_subscribers[task_id].append(queue)
    return queue


def unsubscribe_task(task_id: uuid.UUID, queue: asyncio.Queue):
    """Unsubscribe from task updates."""
    if task_id in _task_subscribers:
        try:
            _task_subscribers[task_id].remove(queue)
            if not _task_subscribers[task_id]:
                del _task_subscribers[task_id]
        except ValueError:
            pass

def dispatch_background(task_id: uuid.UUID, coro):
    loop_task = asyncio.create_task(coro)
    _running_tasks[task_id] = loop_task
    loop_task.add_done_callback(lambda _: _running_tasks.pop(task_id, None))

def cancel_task(task_id: uuid.UUID) -> bool:
    task = _running_tasks.get(task_id)
    if task:
        task.cancel()
        return True
    return False
