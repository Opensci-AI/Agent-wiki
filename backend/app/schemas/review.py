import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ReviewResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    description: str
    affected_pages: list[str]
    search_queries: list[str]
    options: dict[str, Any]
    resolved: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ReviewUpdate(BaseModel):
    resolved: bool | None = None
