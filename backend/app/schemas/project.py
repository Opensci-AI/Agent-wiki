import uuid
from datetime import datetime
from pydantic import BaseModel

class ProjectCreate(BaseModel):
    name: str

class ProjectUpdate(BaseModel):
    name: str | None = None
    purpose: str | None = None
    schema_text: str | None = None

class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    purpose: str
    schema_text: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ProjectListResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
