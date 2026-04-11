import uuid
from datetime import datetime
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    project_id: uuid.UUID
    title: str = "New Conversation"


class ConversationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    conversation_id: uuid.UUID
    role: str = "user"
    content: str


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
