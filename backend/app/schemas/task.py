import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel

class TaskResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    status_detail: str | None = None  # Human-readable: "Extracting text from PDF..."
    current_step: str | None = None   # Machine-readable: "extract_text"
    progress_pct: int
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    model_config = {"from_attributes": True}
