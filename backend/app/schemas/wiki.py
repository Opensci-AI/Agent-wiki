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
