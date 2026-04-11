import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, async_session
from app.models.project import Project
from app.schemas.source import ClipRequest, SourceResponse, SourceListResponse
from app.schemas.task import TaskResponse
from app.services.source_service import upload_source, create_clip, list_sources, get_source, delete_source
from app.core.background import create_task, dispatch_background, update_task_status
from app.services.extraction_service import extract_text, extract_text_async
from app.core.storage import get_storage
from app.api.deps import require_project_owner, require_project_owner_flex

router = APIRouter(prefix="/api/v1/projects/{project_id}/sources", tags=["sources"])


@router.post("/upload", response_model=SourceResponse, status_code=201)
async def upload(project_id: uuid.UUID, file: UploadFile = File(...),
                 project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    data = await file.read()
    source = await upload_source(db, project.id, file.filename or "unnamed", data)

    # Auto-extract text for document types
    text_types = {"pdf", "docx", "pptx", "xlsx", "txt", "md", "csv", "html", "htm", "rtf"}
    if source.content_type in text_types:
        try:
            text = extract_text(data, source.content_type)
            source.extracted_text = text
            source.status = "ready"
            await db.commit()
            await db.refresh(source)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Auto-extract failed for {source.original_name}: {e}")

    return source


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


_MIME_MAP = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
}


@router.get("/{source_id}/file")
async def serve_file(project_id: uuid.UUID, source_id: uuid.UUID,
                     project: Project = Depends(require_project_owner_flex),
                     db: AsyncSession = Depends(get_db)):
    """Serve the raw file content for a source.

    Accepts auth via Authorization header **or** ``?token=`` query param so that
    HTML ``<img>``/``<video>``/``<audio>`` tags can reference this URL directly.
    """
    source = await get_source(db, project.id, source_id)
    storage = get_storage()
    try:
        data = await storage.read(source.storage_path)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=404, detail="File not found in storage")
    mime = _MIME_MAP.get(source.content_type, "application/octet-stream")
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{source.original_name}"'},
    )


@router.delete("/{source_id}", status_code=204)
async def delete(project_id: uuid.UUID, source_id: uuid.UUID,
                 project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    source = await get_source(db, project.id, source_id)
    await delete_source(db, source)


async def _run_extraction(task_id, project_id, source_id, user_id):
    """Background extraction task with LLM support for images."""
    from app.services.config_service import get_effective_config

    try:
        await update_task_status(
            task_id, "running", progress=5,
            detail="Loading file from storage...",
            step="load_file"
        )
        async with async_session() as db:
            source = await get_source(db, project_id, source_id)
            storage = get_storage()
            data = await storage.read(source.storage_path)

            await update_task_status(
                task_id, "running", progress=15,
                detail=f"Loaded {source.original_name} ({len(data):,} bytes)",
                step="file_loaded"
            )

            # Get LLM config for multimodal extraction (images, scanned PDFs)
            config = await get_effective_config(db, user_id)
            llm_config = config.get("llm_config")

            # Determine extraction method
            is_image = source.content_type in ("png", "jpg", "jpeg", "webp", "gif")
            is_pdf = source.content_type == "pdf"

            if is_image:
                await update_task_status(
                    task_id, "running", progress=30,
                    detail="Processing image with Vision AI (OCR)...",
                    step="ocr_image"
                )
            elif is_pdf:
                await update_task_status(
                    task_id, "running", progress=30,
                    detail="Extracting text from PDF...",
                    step="extract_pdf"
                )
            else:
                await update_task_status(
                    task_id, "running", progress=30,
                    detail=f"Extracting text from {source.content_type.upper()}...",
                    step="extract_text"
                )

            # Use async extraction with LLM support
            text = await extract_text_async(data, source.content_type, llm_config)

            # Check if OCR was used (for scanned PDFs)
            if is_pdf and text.startswith("[PDF appears to be scanned"):
                await update_task_status(
                    task_id, "running", progress=50,
                    detail="PDF is scanned, using Vision AI for OCR...",
                    step="ocr_scanned_pdf"
                )
                text = await extract_text_async(data, source.content_type, llm_config)

            await update_task_status(
                task_id, "running", progress=90,
                detail="Saving extracted text...",
                step="save_text"
            )

            source.extracted_text = text
            source.status = "ready"
            await db.commit()

            char_count = len(text)
            word_count = len(text.split())
            await update_task_status(
                task_id, "completed", progress=100,
                result={"chars": char_count, "words": word_count}
            )
    except Exception as e:
        await update_task_status(task_id, "failed", error=str(e))


@router.post("/{source_id}/extract", response_model=TaskResponse, status_code=202)
async def extract(project_id: uuid.UUID, source_id: uuid.UUID,
                  project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    source = await get_source(db, project.id, source_id)
    if source.status == "ready":
        raise HTTPException(status_code=400, detail="Source already extracted")
    task = await create_task(db, project.id, project.owner_id, "extraction", {"source_id": str(source_id)})
    dispatch_background(task.id, _run_extraction(task.id, project.id, source_id, project.owner_id))
    return task
