import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel

class PageCreate(BaseModel):
    path: str
    type: str = "entity"
    title: str
    content: str = ""
    frontmatter: dict[str, Any] = {}

class PageUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    frontmatter: dict[str, Any] | None = None

class PageResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    path: str
    type: str
    title: str
    content: str
    frontmatter: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class PageListResponse(BaseModel):
    id: uuid.UUID
    path: str
    type: str
    title: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
