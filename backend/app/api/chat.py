import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.chat import ConversationCreate, ConversationResponse, MessageResponse
from app.services.chat_service import (
    create_conversation,
    list_conversations,
    get_conversation,
    delete_conversation,
    add_message,
    list_messages,
)
from app.api.deps import get_current_user, require_project_owner
from pydantic import BaseModel

router = APIRouter(tags=["chat"])


class ConversationCreateBody(BaseModel):
    title: str = "New Conversation"


class MessageCreateBody(BaseModel):
    content: str


@router.post(
    "/api/v1/projects/{project_id}/conversations",
    response_model=ConversationResponse,
    status_code=201,
)
async def create_conv(
    body: ConversationCreateBody,
    project: Project = Depends(require_project_owner),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await create_conversation(db, project.id, user.id, body.title)
    return conv


@router.get(
    "/api/v1/projects/{project_id}/conversations",
    response_model=list[ConversationResponse],
)
async def list_convs(
    project: Project = Depends(require_project_owner),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = 0,
    limit: int = 50,
):
    return await list_conversations(db, project.id, user.id, offset, limit)


@router.get(
    "/api/v1/conversations/{conv_id}/messages",
    response_model=list[MessageResponse],
)
async def get_messages(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    # Verify ownership
    await get_conversation(db, conv_id, user.id)
    return await list_messages(db, conv_id, limit)


@router.post(
    "/api/v1/conversations/{conv_id}/messages",
    response_model=MessageResponse,
    status_code=201,
)
async def send_message(
    conv_id: uuid.UUID,
    body: MessageCreateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    await get_conversation(db, conv_id, user.id)
    return await add_message(db, conv_id, "user", body.content)


@router.delete("/api/v1/conversations/{conv_id}", status_code=204)
async def delete_conv(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await get_conversation(db, conv_id, user.id)
    await delete_conversation(db, conv)
