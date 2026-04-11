import uuid
from datetime import datetime
from pydantic import BaseModel


class ClipRequest(BaseModel):
    title: str
    url: str
    content: str


class SourceResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    original_name: str
    content_type: str
    file_size: int
    status: str
    created_at: datetime
    extracted_text: str | None = None
    model_config = {"from_attributes": True}


class SourceListResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_name: str
    content_type: str
    file_size: int
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}
