import uuid
from fastapi import Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User
from app.services.auth_service import get_user_by_id

async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization[7:]
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user

from app.models.project import Project
from sqlalchemy import select

async def require_project_owner(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def get_current_user_flex(
    authorization: str = Header(None, alias="Authorization"),
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate from Authorization header or ?token= query param.

    Useful for endpoints consumed by HTML tags (img/video/audio) that cannot
    send custom headers.
    """
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]
    elif token:
        raw_token = token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_token(raw_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_project_owner_flex(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user_flex),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Like require_project_owner but also accepts ?token= query param."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
