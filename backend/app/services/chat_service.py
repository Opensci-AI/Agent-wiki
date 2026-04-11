import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.conversation import Conversation
from app.models.message import Message


async def create_conversation(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str = "New Conversation",
) -> Conversation:
    conv = Conversation(
        id=uuid.uuid4(),
        project_id=project_id,
        user_id=user_id,
        title=title,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def list_conversations(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.project_id == project_id, Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_conversation(
    db: AsyncSession,
    conv_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user_id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


async def delete_conversation(db: AsyncSession, conv: Conversation) -> None:
    await db.delete(conv)
    await db.commit()


async def add_message(
    db: AsyncSession,
    conv_id: uuid.UUID,
    role: str,
    content: str,
) -> Message:
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        role=role,
        content=content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_messages(
    db: AsyncSession,
    conv_id: uuid.UUID,
    limit: int = 50,
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
